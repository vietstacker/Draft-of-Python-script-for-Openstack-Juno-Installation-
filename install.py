#! /usr/bin/python

import sys
import os
import fcntl
import socket
import subprocess
import time
import struct
import socket





iniparse = None
psutil = None

def get_ip_address():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('google.com',0))
        return s.getsockname()[0]
    except Exception:
        print "Can not get ip address"
        sys.exit(1)

### Kill Process

def kill_process(process_name):
    for proc in psutil.process_iter():
        if proc.name == process_name:
            proc.kill()
            
### Delete file

def delete_file(file_path):
    if os.path.isfile(file_path):
        os.remove(file_path)
    else:
        print "File does not exist"
        
### Write content to file

def write_content_to_file(file_name, content):
    open(file_name, "a").write(content)
    

### Add features into configuration file
def add_config_file (conf_file, section, param, val):
    config = iniparse.ConfigParser()
    config.readfp(open(conf_file))
    if not config.has_section(section):
        config.add_section(section)
        val += '\n'
    config.set(section, param, val)
    with open(conf_file, 'w') as f:
        config.write(f)

def remove_config_file (conf_file, section, param):
    config = iniparse.ConfigParser()
    config.readfp(open(conf_file))
    if param is None:
        config.remove_section(section)
    else:
        config.remove_option(section,param)
    with open(conf_file, 'w') as f:
        config.write(f)
        
def get_param_from_config (conf_file, section, param):
    config = iniparse.ConfigParser()
    config.readfp(open(conf_file))
    if param is None:
        raise Exception ("Parameter is missing")
    else:
        return config.get(section,param)

### Print processes onto screen

def print_format(string):
    print "%s \n"  %("***" *10)
    print "%s" %string


def execution (command, display=False):
    print_format("Executing %s" %command)
    process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr= subprocess.STDOUT)
    if display:
        while True:
            next_line = process.stdout.readline()
            if next_line == '' and process.poll() != None:
                break
            sys.stdout.write(next_line)
            sys.stdout.flush()
            
        output, stderr = process.communicate()
        exitCode = process.returncode
    else:
	output, stderr = process.communicate()
	exitCode = process.returncode

    if exitCode == 0:
        return output.strip()
    else:
        print "Error", stderr
        print "Fail to execute command: %s" %command
        raise Exception(output)


#def database_execution(command):
#    mysql_command = """ mysql -u root -p%s -e "%s" """ % (MYSQL_PASS, command)
#    output = execution(mysql_command)
#    return output


def system_prepare():
    if os.geteuid() != 0:
        sys.exit("Run the script under root")
    execution("apt-get autoclean -y", True)
    execution("apt-get update -y", True)
    execution("apt-get install ubuntu-cloud-keyring python-setuptools python-iniparse python-psutil -y", True)
    execution ("echo deb http://ubuntu-cloud.archive.canonical.com/ubuntu trusty-updates/juno main >> /etc/apt/sources.list.d/ubuntu-cloud-archive-juno-trusty.list")
    execution ("apt-get update && apt-get -y upgrade && apt-get -y dist-upgrade")

    global iniparse
    if iniparse is None:
        iniparse = __import__('iniparse')
    
    global psutil
    if psutil is None:
        psutil = __import__('psutil')
        
def IP_forwarding():
    execution("echo 'net.ipv4.ip_forward = 1' >> /etc/sysctl.conf")
    execution("echo 'net.ipv4.conf.all.rp_filter=0' >> /etc/sysctl.conf")
    execution("echo 'net.ipv4.conf.default.rp_filter=0' >> /etc/sysctl.conf")
    
def NTP_config():
    execution("apt-get install -y ntp")
    execution("sed -i 's/server ntp.ubuntu.com/server 0.vn.pool.ntp.org/g' /etc/ntp.conf")
    execution("sed -i 's/server ntp.ubuntu.com/server 1.vn.pool.ntp.org/g' /etc/ntp.conf")
    execution("sed -i 's/server ntp.ubuntu.com/server 2.vn.pool.ntp.org/g' /etc/ntp.conf")
    execution("sed -i 's/restrict -6 default kod notrap nomodify nopeer noquery/restrict -4 default kod notrap nomodify/g' /etc/ntp.conf")
    execution("sed -i 's/restrict -6 default kod notrap nomodify nopeer noquery/restrict -6 default kod notrap nomodify/g' /etc/ntp.conf")

    time.sleep(3)
    execution("service ntp restart")
    

def install_rabbitmq():
    execution("apt-get install rabbitmq-server -y", True)
    execution("service rabbitmq-server restart", True)
    time.sleep(5)


def install_database():

    execution("bash mysql.sh", True)

def keystone_install_and_configure():
    ip_address = get_ip_address()
    os.environ['SERVICE_TOKEN'] = '%s' %TOKEN_PASS
    os.environ['SERVICE_ENDPOINT'] = 'http://%s:35357/v2.0' %ip_address
     
    time.sleep(2)
    execution("apt-get install keystone -y", True)
    keystone_conf = "/etc/keystone/keystone.conf"

    add_config_file(keystone_conf, "DEFAULT","admin_token","%s" %SERVICE_PASSWORD)
    add_config_file(keystone_conf, "DEFAULT", "admin_port",35357)
    add_config_file(keystone_conf, "DEFAULT", "public_bind_host", "0.0.0.0")
    add_config_file(keystone_conf, "DEFAULT", "admin_bind_host", "0.0.0.0")
    add_config_file(keystone_conf, "DEFAULT", "compute_post", 8774)
    add_config_file(keystone_conf, "DEFAULT", "verbose", "True")
    add_config_file(keystone_conf, "DEFAULT", "log_dir", "/var/log/keystone")

    keystone_mysql = "mysql://keystone:%s@%s/keystone" %(MYSQL_PASS,ip_address) 
    add_config_file(keystone_conf, "database", "connection","%s" %keystone_mysql)
    add_config_file(keystone_conf, "database", "idle_timeout", 3600)
    
    time.sleep(2)
    execution("keystone-manage db_sync")
    execution("service keystone restart", True)
    
#### Keystone Service Installation Starts Here #####


system_prepare()
NTP_config()
IP_forwarding()
install_rabbitmq()

MYSQL_PASS = get_param_from_config("/root/config.cfg","Default","MYSQL_PASS").strip('"')
SERVICE_PASSWORD = get_param_from_config("/root/config.cfg","Default","SERVICE_PASSWORD").strip('"')
TOKEN_PASS = get_param_from_config("/root/config.cfg","Default","TOKEN_PASS").strip('"')

install_database()


keystone_install_and_configure()



