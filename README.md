A container that lets you mount streamable audio content, and exposes an endpoint to adjust the ingress/egress rates

<h1> Quick Start Guide </h1>

First build the docker image

`> docker-compose build mpeg-dash-server`

Next Run the docker image

`> ./launch_server`

Access default content at `http://localhost:8080`. Replace `localhost` with the ip of the computer if accessing it remotely

<h1> Traffic Shaping </h1>

To shape the traffic in/out of the container use port 8088. Example below using wget (cURL works too):

Set ingress/egress rate to 1 megabit/s
`> wget -qO- http://localhost:8088?rate=1000`

Set ingress/egress rate to 100 kilobits/s
`> wget -q0- http://localhost:8088?rate=100`


<h1> How to configure container </h1>

Mounting custom content on the server

`> ./launch_server.sh -v /path/to/custom/media:/dash_contents`

Mounting media content to a custom port on your host, e.g 9000 

`> ./launch_server.sh -p 9000:8080`
  
Mounting rate-handling server to a custom port on your host, e.g 9001

`> ./launch_server.sh -p 9001:8088`
  

<h1> Common issues </h1>

The container is dependent on the linux kernel ifb module. Downlink ingress rate adjustments won't work on macs
