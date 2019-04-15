# investigate grabbing date/time in output filename so that we get a unique
# filename after every run

import paramiko
from getpass import getpass
import re
import sys
import time
from pprint import pprint
import datetime

ssh_client = paramiko.SSHClient()
ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
# regex patterns for later use
tx_pause_pattern = re.compile('([0-9]{1,20}) Tx')
eth_pattern = re.compile('Eth([0-9]{3})')
int_pattern = re.compile('([a-zA-Z]{1,3}[0-9]{1,3}/[0-9]{1,2}/?[0-9]{1,2})')

# switch commands assigned to variables for later use
fex_command = 'show fex'
po_command = 'show int po'
po_summ_command = 'show port-channel summary\n'

# function to establish persistent SSH session
def ssh_connect(ip):
    ssh_client = paramiko.SSHClient()
    ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh_client.connect(hostname=ip,
                       username=username,
                       password=password)
    session = ssh_client.invoke_shell()
    return session

# function to take in data, search for a regex pattern and return a matched value
def parse(response, pattern):
    raw_output = response.decode()
    match = pattern.search(raw_output)
    if match:
        matched_value = match.group(0)
        return matched_value

# get creds from user
username = input('Username: ')
password = getpass('Password: ')

now = datetime.datetime.now()
print(now)
year = str(now.year)
month = str(now.month)
day = str(now.day)
hour = str(now.hour)
minute = str(now.minute)
filetime = (f"{year}-{month}-{day} {hour}.{minute}")

# read in list of switch IPs from file
file = open('dc1-5ks-list.txt', 'r')
for line in file:
    device_ip_list = line.strip().split(',')
pprint(device_ip_list)
file.close()

# create csv file for program output
final_file = open(f'TxPause{filetime}.csv', 'w+')
final_file.write('Switch_IP,FEX,Tx_Pause_Count\n')

# cycle through list of switch IPs, get list of Port Channels
for ip in device_ip_list:
    session = ssh_connect(ip)
    print('-----Logging into ' +ip)
    session.send('terminal length 0\n')
    time.sleep(1)
    session.send(po_summ_command)
    time.sleep(2)
    output = session.recv(10000)
    raw_output = output.decode()
    po_lines = raw_output.split('\r\n')
    del po_lines[0:24]
    del po_lines[-1]
    pprint(po_lines)
    fex_list = []
    tru_fex_list = []
    # cycle through port channels output and separate the fex numbers
    for line in po_lines:
        device_list = line.split(' ')
        fex_list.append(device_list[0])
    # cycle through fex numbers, remove None entries to get a true list of fexes
    for x in fex_list:
        if x != '':
            tru_fex_list.append(x)
    pprint(tru_fex_list)
    # cycle through true fex list and search for Tx pauses
    for fex in tru_fex_list:
        fex_num = int(fex)
        if fex_num >= 1000:
            session.send('terminal length 0\n')
            time.sleep(1)
            session.send(po_command + fex +' | incl Tx\n')
            time.sleep(3)
            stdout = session.recv(1000)
            raw_output = stdout.decode()
            match = tx_pause_pattern.search(raw_output)
            if match:
                matched_value = match.group(0)
                matched_list = matched_value.split(' ')
                tx_pause_count = int(matched_list[0])
                print(f'Switch {ip} Port-channel {fex} has {tx_pause_count} Tx pauses')
                # If Tx pause found, get port channel members
                if tx_pause_count > 0:
                    session.send('terminal length 0\n')
                    time.sleep(1)
                    session.send(po_command+fex+' | incl Members\n')
                    time.sleep(3)
                    ssh_output = session.recv(1000)
                    raw_output = ssh_output.decode()
                    members_list = raw_output.split('channel: ')
                    int_list = members_list[1].split(', ')
                    fexes_list = []
                    # parse PO members interfaces to get just list of fex numbers
                    for y in int_list:
                        fex_int = y.split('//')
                        fexes_list.append(fex_int[0])
                    # print info about PO and fex members and append to output file
                    for x in fexes_list:
                        match = eth_pattern.search(x)
                        if match:
                            parent_fex = match.group(1)
                            print(f'The Parent switch for PO{fex_num} is FEX{parent_fex}')
                            tx_string = str(tx_pause_count)
                            parent_string = str(parent_fex)

                            final_file.write(ip+',FEX'+parent_string+','+tx_string+'\n')
    session.close()

final_file.close()
