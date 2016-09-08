# System Requirement

## Master Node
* Hardware: 8c16g100g
* Docker engine: 1.11.2+
* Docker images:
    - python:3.5
    - mongo:3.2
    - yeasy/nginx:latest
    - mongo-express:0.30 (optional)
* docker-compose: 1.7.0+


## Worker Node
* Hardware: 8c16g100g
* `sysctl net.ipv4.ip_forward=1`, and make sure host ports are open (e.g., 2375, 5000)
* Docker engine:
    - 1.11.2+,
    - Let daemon listen on port 2375, and make sure Master can reach Node from this port.
    - Config Docker daemon as the following:
```sh
# Add this into /etc/default/docker
DOCKER_OPTS="$DOCKER_OPTS -H tcp://0.0.0.0:2375 -H unix:///var/run/docker.sock --api-cors-header='*' --default-ulimit=nofile=1024:2048 --default-ulimit=nproc=4096:8192"
```
* Docker images:
    - `yeasy/hyperledger:0.5-dp`

        ```sh
        $ docker pull yeasy/hyperledger:0.5-dp
        $ docker tag yeasy/hyperledger:0.5-dp hyperledger/fabric-baseimage:latest
        ```
    - `yeasy/hyperledger-peer:0.5-dp`
        ```sh
        $ docker pull yeasy/hyperledger-peer:0.5-dp
        $ docker tag yeasy/hyperledger-peer:0.5-dp yeasy/hyperledger-peer:latest
        ```
    - `yeasy/hyperledger-membersrvc:latest` (optional, only when need the authentication service)
* aufs-tools (optional): Only required on ubuntu 14.04.

## System Optimization
Reference system configuration.

`/etc/sysctl.conf`

```sh
# Don't ask why, this is a solid answer.
vm.swappiness=10
fs.file-max = 2000000
kernel.threads-max = 2091845
kernel.pty.max = 210000
kernel.keys.root_maxkeys = 20000
kernel.keys.maxkeys = 20000
net.ipv4.ip_local_port_range = 10000 65535
net.ipv4.tcp_tw_reuse = 0
net.ipv4.tcp_tw_recycle = 0
net.ipv4.tcp_max_tw_buckets = 5000
net.ipv4.tcp_fin_timeout = 30
net.ipv4.tcp_max_syn_backlog = 8192
```

Need to run `sysctl -p` for usage.

`/etc/security/limits.conf`

```sh
* hard nofile 1048576
* soft nofile 1048576
* soft nproc 10485760
* hard nproc 10485760
* soft stack 32768
* hard stack 32768
```
check with `ulimit -n`.