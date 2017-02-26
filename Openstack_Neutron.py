_author_ = "Bassim Aly"

import requests
import json
from netmiko import *


mode = "staging"

if mode == "staging":
    OS_URL = "192.168.1.120"
    OS_USERNAME = "admin"
    OS_PASSWORD = "xxxxxxx"


OS_TENANT = "admin"
keystone_port = 5000

neutron_host = {"device_type": "linux",
               "ip": OS_URL,
               "username": "root",
               "password": OS_PASSWORD,
               'verbose': False,
               }

token_url = "http://{0}:{1}/v2.0/tokens" .format(OS_URL,keystone_port)
token_head = {'Content-Type': 'application/json',
        'Accept':'application/json'}

token_payload = {"auth":
                     {"passwordCredentials": {"username": OS_USERNAME,
                                              "password": OS_PASSWORD,
                                             },
                      "tenantName":OS_TENANT
                     },
                 }
token_response = requests.post(token_url,
                               headers=token_head,
                               data=json.dumps(token_payload)
                               )

if token_response.status_code == 200:
    token = token_response.json()['access']['token']['id']
    tenant_id = token_response.json()['access']['token']['tenant']['id']
    compute_adminURL = token_response.json()['access']['serviceCatalog'][0]['endpoints'][0]['adminURL']
    neutron_adminURL = token_response.json()['access']['serviceCatalog'][1]['endpoints'][0]['adminURL']
    cinder_adminURL = token_response.json()['access']['serviceCatalog'][2]['endpoints'][0]['adminURL']
    glance_adminURL = token_response.json()['access']['serviceCatalog'][4]['endpoints'][0]['adminURL']

    req_header = {'X-Auth-Token': token}

    flavors = requests.get(compute_adminURL + "/flavors", headers=req_header)
    instances = requests.get(compute_adminURL + "/servers/detail?all_tenants=1", headers=req_header)
    ports = requests.get(neutron_adminURL + "/v2.0/ports", headers=req_header)
    networks = requests.get(neutron_adminURL + "/v2.0/networks", headers=req_header)
else:
    print "connection encountered an error. Please run tcpdump or any network utility for further troubleshooting"

def GetInstancesDetailsByName(name):
    instance_macs = []
    instance_ips = []
    port_prefix = []
    for item in instances.json()["servers"]:
        if item["name"] == name:
            addresses = item["addresses"]
            for key,value in addresses.iteritems():
                instance_macs.append(value[0]["OS-EXT-IPS-MAC:mac_addr"])
                instance_ips.append(value[0]["addr"])
    for mac in instance_macs:
        for item in ports.json()["ports"]:
            if item["mac_address"] == mac:
                port_ip_address = item["dns_assignment"][0]["ip_address"]
                port_prefix.append(item["id"][:11])
    return instance_ips,instance_macs,port_prefix


def GetOVSDetailsByMAC(mac):
    net_connect = ConnectHandler(**neutron_host)
    ovs_int_actions = net_connect.send_command('ovs-ofctl dump-flows br-int | egrep -v "resubmit|icmp6" | grep -i {0} | cut -d "," -f7,8,9,10,11' .format(mac))
    ovs_int_port = net_connect.send_command('ovs-appctl fdb/show br-int | grep -i {0} | cut -d " " -f5'.format(mac))
    ovs_ext_port = net_connect.send_command('ovs-appctl fdb/show br-ex | grep -i {0} | cut -d " " -f5'.format(mac))
    ovs_int_vlan = net_connect.send_command('ovs-appctl fdb/show br-int | grep -i {0} | cut -d " " -f10'.format(mac))
    ovs_ext_vlan = net_connect.send_command('ovs-appctl fdb/show br-ex | grep -i {0} | cut -d " " -f10'.format(mac))
    ovs_ext_actions = net_connect.send_command('ovs-ofctl dump-flows br-ex | egrep -v "resubmit|icmp6" | grep -i dl_vlan={0} | cut -d "," -f7,8,9,10,11' .format(ovs_int_vlan))

    return ovs_int_port,\
           ovs_int_vlan, \
           ovs_int_actions, \
           ovs_ext_port, \
           ovs_ext_vlan, \
           ovs_ext_actions



def Report(instance):
    output = "----------------------------------------------------- Instance Name : {0} ---------------------------------------------------------" .format(instance) + "\n"
    instance_ips, instance_macs, prefix = GetInstancesDetailsByName(instance)
    for index,mac in enumerate(instance_macs):
        ovs_int_port,\
        ovs_int_vlan,\
        ovs_int_actions,\
        ovs_ext_port,\
        ovs_ext_vlan,\
        ovs_ext_actions = GetOVSDetailsByMAC(mac)
        output += ">> ip={0}" .format(instance_ips[index]) + " mac={0}" .format(mac) + " prefix={0}" .format(prefix[index]) + "\n" + \
                  "   ovs_int_port={0}" .format(ovs_int_port) +  "   ovs_int_vlan={0}" .format(ovs_int_vlan) + "   ovs_int_action={0}" .format(ovs_int_actions) + "\n" + \
                  "   ovs_ext_port={0}".format(ovs_ext_port) + "   ovs_ext_vlan={0}".format(ovs_ext_vlan) + "   ovs_ext_action={0}".format(ovs_ext_actions) + "\n\n"
    return output

print Report("esc200")