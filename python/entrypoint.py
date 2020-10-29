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
LATENCY_ENDPOINT = "delay"
JITTER_ENDPOINT = "jitter"
PACKET_ERROR_ENDPOINT = "packet_error"
VERY_HIGH_RATE_KBITS = 80000
DEFAULT_RATE_KBITS = VERY_HIGH_RATE_KBITS
DEFAULT_LATENCY_MS = 0
DEFAULT_JITTER_MS = 0
DEFAULT_PACKET_ERROR_RATE_PERCENT = 0

#Commands
TRAFFIC_SHAPER_CLEAR_COMMAND = "/wondershaper -ca eth0"
TRAFFIC_SHAPER_RATE_COMMAND = "/wondershaper -a eth0 -u {rate} -d {rate}"
TRAFFIC_SHAPER_PACKET_ERROR_OPTION = " -e {}"
TRAFFIC_SHAPER_LATENCY_OPTION = " -l {}"
TRAFFIC_SHAPER_JITTER_OPTION = " -j {}"
CONTENT_PORT = 8080
RATE_HANDLER_PORT = 8088

#Valid Endpoints for Traffic Shaping
DEFAULT_VALUES = \
    {EGRESS_ENDPOINT: DEFAULT_RATE_KBITS,
     LATENCY_ENDPOINT: DEFAULT_LATENCY_MS,
     JITTER_ENDPOINT: DEFAULT_JITTER_MS,
     PACKET_ERROR_ENDPOINT: DEFAULT_PACKET_ERROR_RATE_PERCENT}



def shape_traffic(rate, delay=10, jitter=0, packet_error=0):
    """
    Shapes traffic. Rate is mandatory, other settings are optional.

    :param rate: Packet rate in kbits/second
    :type rate: Int
    :param delay: Delay in ms, defaults to 0
    :type delay: int, optional
    :param jitter: Delay Jitter in ms, defaults to 0. I.e 10 ms delay +/- jitter
        ms
    :type jitter: int, optional
    :param packet_error_percent: Packet error rate in percent, defaults to 0
        min accuracy of .1%
    :type packet_error_percent: int/float, optional
    """
    net_em_append_base=""
    if delay:
        net_em_append_base += TRAFFIC_SHAPER_LATENCY_OPTION.format(delay)
    if jitter and net_em_append_base:
        net_em_append_base += TRAFFIC_SHAPER_JITTER_OPTION.format(jitter)
    if packet_error:
        net_em_append_base += \
            TRAFFIC_SHAPER_PACKET_ERROR_OPTION.format(packet_error)
    cmd = TRAFFIC_SHAPER_RATE_COMMAND.format(rate=rate, percent=0) + \
        net_em_append_base
    logger.info("Wondershaper Command: %s", cmd)
    os.system(TRAFFIC_SHAPER_CLEAR_COMMAND)
    os.system(cmd)

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
        self.data = dict(DEFAULT_VALUES)
        shape_traffic(**self.data)

    def render_GET(self, request):
        """
        Adjusts the following endpoints to user-specified values:
            `rate`: Sets egress/ingress rates (default 8000 kbits/s)
            `packet_error`: Packet Error raate (default 0%)
            `delay`: Packet delay in ms (default 0ms)
            `jitter`: Packet delay jitter (delay +/- jitter ms, default 0ms)
        Args:
            request (request object): request object
        """
        logger.info("Request args %s", request.args.keys())

        # Find the common set of keys between what is valid and what was sent
        # To the server
        common_endpoints = list(set(self.data.keys()) &
                                set(request.args.keys()))

        # Iterate through data and compare against what's stored
        changed = False
        for endpoint in common_endpoints:
            try:
                val = int(request.args[endpoint][0])
            except ValueError:
                logger.error("Invalid {} parameter passed in".format(endpoint))
                return "{} Value Error\n".format(endpoint)
            if self.data[endpoint] != val:
                logger.info("Adjusting %s: %s", endpoint, val)
                self.data[endpoint] = val
                changed = True
        if changed:
            shape_traffic(**self.data)

        ret_val = "Received:\n"
        for endpoint in common_endpoints:
            ret_val += "{}={} \n".format(endpoint, self.data[endpoint])
        ret_val += "\n"
        return ret_val


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
