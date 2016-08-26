#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os

# os.system("git clone https://github.com/bitcoin/bitcoin src/bitcoin")

## check system for dependencies
# git
def check_dependencies():
    if (os.system('docker version') != 0):
        # sudo gpasswd -a ${USER} docker; sudo service docker restart; newgrp docker
        exit("docker not found or not accessible")

# check_dependencies()
# etc

# IP range from RFC6890
# it does not conflict with https://github.com/bitcoin/bitcoin/blob/master/src/netbase.h
ip_range = "240.0.0.0/4"
ip_bootstrap = "240.0.0.2"

image = 'btn/base:v2'
conatiner_prefix = 'btn-'
number_of_conatiners = 10
number_of_blocks = '6'

# python
# import os

def bitcoindCmd (strategy = 'default'):
    daemon = ' bitcoind '
    default = {
          'regtest': ' -regtest ',       # activate regtest mode
          'datadir': ' -datadir=/data ', # change the datadir
          'debug': ' -debug ',           # log all events
          #'printtoconsole': ' -printtoconsole ', # print the log to stdout instead of a file TODO `docker logs`
          'logips': ' -logips ',         # enable ip loging
          'listen' : ' -listen ',        # ensure listening even if 'connect' is given
          'listenonion' : ' -listenonion=0 ', # disable tor 
          'onlynet': ' -onlynet=ipv4 ',  # disable ipv6
    }
    configs = {
        'default': {},
        'bootstrap' : {
            'disablewallet': ' -disablewallet=1 ' # disable wallet
        },
        'user': {
            'dnsseed' : ' -dnsseed=0 ',  # disable dns seed lookups, otherwise this gets seeds even with docker --internal network
            'addnode' : ' -addnode=' + ip_bootstrap + ' ', # only connect ourself introductionary node
            'seednode': ' -seednode=240.0.0.3 ',
            'keypool' : ' -keypool=1 '
        },
        'miner-solo' : {
            'addnode' : ' -addnode=fst ', # only connect to ourself introductionary node
            'keypool' : ' -keypool=1 '
        }
    }
    default.update(configs[strategy])
    return  daemon + ( ' '.join(default.values()) )

def dockerBootstrapCmd (cmd):
    return (' '
    ' docker run '
    '   --detach=true '
    '   --net=isolated_nw '
    '   --ip=' + ip_bootstrap + ' '
    '   --name=bootstrap'   # conatiner name
    '   ' + image + ' '      # image name # src: https://hub.docker.com/r/abrkn/bitcoind/
    '   ' + cmd + ' '
    ' '
    )

def dockerNodeCmd (name,cmd):
    return (' '
    ' docker run '
    '   --cap-add=NET_ADMIN ' # for `tc`
    '   --detach=true '
    '   --net=isolated_nw '
    '   --name=' + name + ' '   # conatiner name
    '   --hostname=' + name + ' '
    '   --volume $PWD/datadirs/' + name + ':/data '
    '   ' + image + ' '      # image name # src: https://hub.docker.com/r/abrkn/bitcoind/
    '   bash -c "' + cmd + '" '
    ' '
    )

def cli(node,command):
    return (' '
    ' docker exec ' 
    + node + 
    ' bitcoin-cli -regtest -datadir=/data '
    + command +
    ' '
    )

def nodeInfo(node):
    commands = [
#        'getconnectioncount',
#        'getblockcount',
#        'getinfo',
#        'getmininginfo',
        'getpeerinfo'
    ]
    return ';'.join([cli(node,cmd) for cmd in commands])


def dockerStp (name):
    return (' '
    ' docker rm --force ' + name + ' & '
    ' '
    )

def status():
    import subprocess
    batcmd = cli('bootstrap','getpeerinfo')
    result = subprocess.check_output(batcmd, shell=True)

    import json
    import codecs
    pretty = json.loads(str(result))
    return [ node['synced_headers'] for node in pretty]

# src https://github.com/dcm-oss/blockade/blob/master/blockade/net.py
def slow_network(cmd):
    traffic_control = "tc qdisc replace dev eth0 root netem delay 1000ms"
    return traffic_control + "; " + cmd
    # apt install iproute2
    # --cap-add=NET_ADMIN

# create execution plan
import array
plan = []

class Network():
    def __enter__(self):
        plan.append('docker network create --subnet=' + ip_range + ' --driver bridge isolated_nw ; sleep 1')
    def __exit__(self):
        plan.append('docker network rm isolated_nw')

class Nodes():
    def __init__(self):
        self.ids = [ conatiner_prefix + str(element) for element in range(number_of_conatiners)]
        self.nodes = [ dockerNodeCmd(id,slow_network(bitcoindCmd('user'))) for id in self.ids ]
    def __enter__(self):
        plan.append( dockerBootstrapCmd(slow_network(bitcoindCmd('user'))) )
        plan.extend( self.nodes )
        plan.append('sleep 2') # wait before generating otherwise "Error -28" (still warming up)
    def __exit__(self):
        plan.extend( [ dockerStp(id) for id in self.ids] )
        plan.append( dockerStp('bootstrap') )
        plan.append('sleep 5')

# setup network

# setup nodes

with Network():
    with Nodes() as nds:
        os.system("rm -rf ./datadirs/*")

        plan.append(cli(nds.ids[1],'generate ' + number_of_blocks))
        plan.append('sleep 10') # wait for blocks to spread

        plan.append('docker run --rm --volume $PWD/datadirs:/data ' + image + ' chmod a+rwx --recursive /data') # fix permissions on datadirs

print('\n'.join(plan))
[os.system(cmd) for cmd in plan] 

def runAnalytics():
    os.system(' '
    ' docker run --name elastic --detach elasticsearch:2.3.5 '
    ' ; docker run --name kibana --detach --link elastic:elasticsearch --publish 5601:5601 kibana:4.5.4 '
    ' ; docker run --name logstash --rm --link elastic:elastic -v "$PWD":/data logstash:2.3.4-1 logstash -f /data/docker/logstash.conf '
    ' '
    )

    os.system(' '
    ' docker rm --force elastic kibana'
    ' '
    )

runAnalytics()