docker run -it -p 8080:8080 -p 8088:8088 -v /lib/modules:/lib/modules --privileged --cap-add=NET_ADMIN $@ mpeg-dash-server
