#!/usr/bin/env python
"""
Webserver entry point
"""

import logging
import signal
import sys
import os
import threading
import netifaces
from enum import Enum
from twisted.web import resource, static, server
from twisted.internet import reactor

# System Constants
logging.basicConfig(stream=sys.stdout,
                    format='%(asctime)s [%(levelname)s] %(message)s',
                    level='INFO')
logger = logging.getLogger('DASH_WEBSERVER.{}'.format(__name__))
SERVER_FILE_PATH = "/dash_contents"
DASH_STREAM_FILE = "stream.mpd"
EGRESS_ENDPOINT = "rate"
VERY_HIGH_RATE_KBITS = 8000
DEFAULT_RATE_KBITS = VERY_HIGH_RATE_KBITS
TRAFFIC_SHAPER_CLEAR_COMMAND = "/wondershaper -ca eth0"
TRAFFIC_SHAPER_COMMAND = "/wondershaper -a eth0 -u {rate} -d {rate}"
CONTENT_PORT = 8080
RATE_HANDLER_PORT = 8088

def shape_traffic(rate):
    """
    Does traffic shaping inside the container

    Args:
        rate (int): [description]
    """
    os.system(TRAFFIC_SHAPER_CLEAR_COMMAND)
    os.system(TRAFFIC_SHAPER_COMMAND.format(rate=rate))

def get_host_ip():
    """
    Helper function to get the host ip

    Returns:
        String: IP Address
    """
    addrs = netifaces.ifaddresses('eth0')
    return addrs[netifaces.AF_INET][0]['addr']

class RateHandler(resource.Resource):
    """
    Wrapper class to handle ingress/egress-rate adjustments. Rate is symmetric
        for both uplink and downlink
    """
    isLeaf = True

    def __init__(self):
        """
        Egress handler to shape in/outbound traffic from container

        Args:
            path (string): Directory to files that are being shared
        """
        self.curr_rate = DEFAULT_RATE_KBITS
        shape_traffic(self.curr_rate)

    def render_GET(self, request):
        """
        Adjusts the egress rate of the server to a user-specified value

        Args:
            request (request object): request object
        """
        logger.info("Request args %s", request.args.keys())
        if EGRESS_ENDPOINT in request.args.keys():
            try:
                rate = int(request.args[EGRESS_ENDPOINT][0])
            except ValueError:
                logger.error("Invalid rate parameter passed in")
                return "Rate Value Error\n"
            if self.curr_rate != rate:
                logger.info("Adjusting egress rate: %s", rate)
                shape_traffic(rate)
                self.curr_rate = rate
        return "Rate={}\n".format(self.curr_rate)


class ContentServer(threading.Thread):
    """
    Content Server class. Encapsulates all active ports on the server
    """

    def __init__(self, handlers=[], ports=[]):
        """
        Initializes instance of ContentServer

        Args:
            handlers (list of twisted.web.resource.Resource instances,
                optional): A list of service handlers hosted on this server.
                Defaults to []
            ports (list of int, optional): A list of ports that map 1-to-1 to
                the handlers
        """
        self.handlers = handlers
        self.ports = ports
        self.port_listeners = []
        assert len(handlers) == len(ports), \
            "Must specify a unique port per handler"
        self._init_handlers()
        threading.Thread.__init__(self, name="ContentServer")
        self.daemon = True

    def _init_handlers(self):
        """
        Initialize any content handlers, and create any port listener objects
        """
        for handler, port in zip(self.handlers, self.ports):
            self.add_handler(handler, port)

    def add_handler(self, handler, port):
        """
        Creates a port listener for a given handler and port

        Args:
            handler (twisted.web.resource.Resource): Content handler
            port (int): Port to access the content
        """
        s = server.Site(handler)
        self.port_listeners.append(reactor.listenTCP(port, s,
                                                     interface=get_host_ip()))

    def run(self):
        """
        Starts the WebServer thread
        """
        logger.info("Starting all services on the webserver!")
        if (self.port_listeners):
            reactor.run(installSignalHandlers=False)

    def shutdown(self):
        """
        Stops the webserver thread
        """
        for pl in self.port_listeners:
            pl.stopListening()
        reactor.stop()


def main():
    """
    Main run loop. Starts a dash-content server and a traffic-shaping server
    """

    # Create hosting service
    handlers = [static.File(SERVER_FILE_PATH), RateHandler()]
    ports = [CONTENT_PORT, RATE_HANDLER_PORT]
    host = ContentServer(handlers, ports)

    # Start the webserver
    host.start()

    # Run until we receive a sig-term
    global shutting_down
    shutting_down = False

    logger.info("Starting main run loop")
    # Main run loop
    while not shutting_down:
        # set up a signal handler to trigger shutdown process
        def stop(*args):
            logger.info('Received SIGTERM')
            global shutting_down
            shutting_down = True
        signal.signal(signal.SIGTERM, stop)
    host.shutdown()
    logger.info('Shutting down')

if __name__ == '__main__':
    main()
