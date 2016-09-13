# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

#*** nmeta - Network Metadata - TC Static Class and Methods

"""
This module is part of the nmeta suite running on top of Ryu SDN controller
to provide network identity and flow (traffic classification) metadata
"""

import logging
import logging.handlers
import struct
import time
import sys

#*** Import netaddr for IP address checking:
from netaddr import IPAddress
from netaddr import IPNetwork
from netaddr import EUI
from netaddr import iter_iprange

#*** Ryu imports:
from ryu.lib import addrconv
from ryu.lib.packet import packet
from ryu.lib.packet import ethernet
from ryu.lib.packet import lldp
from ryu.lib.packet import ipv4
from ryu.lib.packet import tcp

#*** nmeta imports:
import nmisc

class StaticInspect(object):
    """
    This class is instantiated by tc_policy.py 
    (class: TrafficClassificationPolicy) and provides methods to 
    query static traffic classification matches
    """
    def __init__(self, _config):
        #*** Get logging config values from config class:
        _logging_level_s = _config.get_value \
                                    ('tc_static_logging_level_s')
        _logging_level_c = _config.get_value \
                                    ('tc_static_logging_level_c')
        _syslog_enabled = _config.get_value ('syslog_enabled')
        _loghost = _config.get_value ('loghost')
        _logport = _config.get_value ('logport')
        _logfacility = _config.get_value ('logfacility')
        _syslog_format = _config.get_value ('syslog_format')
        _console_log_enabled = _config.get_value ('console_log_enabled')
        _console_format = _config.get_value ('console_format')
        #*** Set up Logging:
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)
        self.logger.propagate = False
        #*** Syslog:
        if _syslog_enabled:
            #*** Log to syslog on host specified in config.yaml:
            self.syslog_handler = logging.handlers.SysLogHandler(address=(
                                                _loghost, _logport), 
                                                facility=_logfacility)
            syslog_formatter = logging.Formatter(_syslog_format)
            self.syslog_handler.setFormatter(syslog_formatter)
            self.syslog_handler.setLevel(_logging_level_s)
            #*** Add syslog log handler to logger:
            self.logger.addHandler(self.syslog_handler)
        #*** Console logging:
        if _console_log_enabled:
            #*** Log to the console:
            self.console_handler = logging.StreamHandler()
            console_formatter = logging.Formatter(_console_format)
            self.console_handler.setFormatter(console_formatter)
            self.console_handler.setLevel(_logging_level_c)
            #*** Add console log handler to logger:
            self.logger.addHandler(self.console_handler)
       
    def check_static(self, policy_attr, policy_value, pkt):
        """
        Passed a static classification attribute, value and packet and
        return 1 for is match and 0 for not a match or any type of error
        """
        pkt_eth = pkt.get_protocol(ethernet.ethernet)
        pkt_ip4 = pkt.get_protocol(ipv4.ipv4)
        pkt_tcp = pkt.get_protocol(tcp.tcp)
        if (policy_attr == 'eth_src'):
            if pkt_eth:
                return self.is_match_macaddress(pkt_eth.src, policy_value)
            else:
                return 0
        elif (policy_attr == 'eth_dst'):
            if pkt_eth:
                return self.is_match_macaddress(pkt_eth.dst, policy_value)
            else:
                return 0
        elif (policy_attr == 'eth_type'):
            if pkt_eth:
                return self.is_match_ethertype(pkt_eth.ethertype, policy_value)
            else:
                return 0
        elif (policy_attr == 'ip_src'):
            if pkt_ip4:
                if pkt_ip4.src:
                    return self.is_match_ip_space(pkt_ip4.src, policy_value)
                else:
                    return False
        elif (policy_attr == 'ip_dst'):
            if pkt_ip4:
                if pkt_ip4.dst:
                    return self.is_match_ip_space(pkt_ip4.dst, policy_value)
                else:
                    return False   
        elif (policy_attr == 'tcp_src'):
            if pkt_tcp:
                if pkt_tcp.src_port == policy_value:
                    return True
                else:
                    return False                     
        elif (policy_attr == 'tcp_dst'):
            if pkt_tcp:
                if pkt_tcp.dst_port == policy_value:
                    return True
                else:
                    return False   
        else:
            #*** didn't match any policy conditions so return false and
            #***  log an error:
            self.logger.error("Policy attribute %s "
                                  "did not match", policy_attr)            
            return False                           

    def is_valid_macaddress(self, value_to_check):
        """
        Passed a prospective MAC address and check that
        it is valid.
        Return 1 for is valid IP address and 0 for not valid
        """
        try:
            if not EUI(value_to_check):
                self.logger.debug("Check of "
                        "is_valid_macaddress on %s returned false",
                        value_to_check)
                return 0
        except:
            self.logger.debug("Check of "
                    "is_valid_macaddress on %s raised an exception", 
                    value_to_check)
            return 0
        return 1

    def is_valid_ethertype(self, value_to_check):
        """
        Passed a prospective EtherType and check that
        it is valid. Can be hex (0x*) or decimal
        Return 1 for is valid IP address and 0 for not valid
        """
        if value_to_check[:2] == '0x':
            #*** Looks like hex:
            try:
                if not (int(value_to_check, 16) > 0 and \
                               int(value_to_check, 16) < 65536):
                    self.logger.debug("Check of "
                        "is_valid_ethertype as hex on %s returned false",
                        value_to_check)
                    return 0
            except:
                self.logger.debug("Check of "
                    "is_valid_ethertype as hex on %s raised an exception", 
                        value_to_check)
                return 0
        else:
            #*** Perhaps it's decimal?
            try:
                if not (int(value_to_check) > 0 and \
                                  int(value_to_check) < 65536):
                    self.logger.debug("Check of "
                        "is_valid_ethertype as decimal on %s returned false",
                        value_to_check)
                    return 0
            except:
                self.logger.debug("Check of "
                    "is_valid_ethertype as decimal on %s raised an exception", 
                        value_to_check)
                return 0
        return 1
        
    def is_valid_ip_space(self, value_to_check):
        """
        Passed a prospective IP address and check that
        it is valid. Can be IPv4 or IPv6 and can be range or have CIDR mask
        Return 1 for is valid IP address and 0 for not valid
        """
        #*** Does it look like a CIDR network?:
        if "/" in value_to_check:
            try:
                if not IPNetwork(value_to_check):
                    self.logger.debug("Network check "
                        "of is_valid_ip_space on %s returned false",
                        value_to_check)
                    return 0
            except:
                self.logger.debug("Network check of "
                    "is_valid_ip_space on %s raised an exception", 
                    value_to_check)
                return 0
            return 1
        #*** Does it look like an IP range?:
        elif "-" in value_to_check:
            ip_range = value_to_check.split("-")
            if len(ip_range) != 2:
                self.logger.debug("Range check of "
                    "is_valid_ip_space on %s failed as not 2 items in list", 
                    value_to_check)
                return 0
            try:
                if not (IPAddress(ip_range[0]) and IPAddress(ip_range[1])):
                    self.logger.debug("Range check "
                        "of is_valid_ip_space on %s returned false",
                        value_to_check)
                    return 0
            except:
                self.logger.debug("Range check of "
                    "is_valid_ip_space on %s raised an exception", 
                    value_to_check)
                return 0
            #*** Check second value in range greater than first value:
            if IPAddress(ip_range[0]).value >= IPAddress(ip_range[1]).value:
                self.logger.debug("Range check of "
                    "is_valid_ip_space on %s failed as range is negative", 
                    value_to_check)
                return 0
            #*** Check both IP addresses are the same version:
            if IPAddress(ip_range[0]).version != \
                                 IPAddress(ip_range[1]).version:
                self.logger.debug("Range check of "
                    "is_valid_ip_space on %s failed as IP versions are "
                    "different", value_to_check)
                return 0
            return 1
        else:
            #*** Or is it just a plain simple IP address?:
            try:
                if not IPAddress(value_to_check):
                    self.logger.debug("Check of "
                        "is_valid_ip_space on %s returned false",
                        value_to_check)
                    return 0
            except:
                self.logger.debug("Check of "
                    "is_valid_ip_space on %s raised an exception", 
                    value_to_check)
                return 0
        return 1

    def is_valid_transport_port(self, value_to_check):
        """
        Passed a prospective TCP or UDP port number and check that
        it is an integer in the correct range.
        Return 1 for is valid port number and 0 for not valid port
        number
        """
        try:
            if not (int(value_to_check)>0 and int(value_to_check)<65536):
                self.logger.debug("Check of "
                    "is_valid_transport_port on %s returned false",
                    value_to_check)
                return 0
        except:
            self.logger.debug("Check of "
                "is_valid_transport_port on %s raised an exception", 
                value_to_check)
            return 0
        return 1

    def is_match_macaddress(self, value_to_check1, value_to_check2):
        """
        Passed a two prospective MAC addresses and check to
        see if they are the same address.
        Return 1 for both the same MAC address and 0 for different
        """
        try:
            if not EUI(value_to_check1) == EUI(value_to_check2):
                self.logger.debug("Check of "
                        "is_match_macaddress on %s vs %s returned false",
                        value_to_check1, value_to_check2)
                return 0
        except:
            self.logger.debug("Check of "
                    "is_match_macaddress on %s vs %s raised an exception", 
                    value_to_check1, value_to_check2)
            return 0
        return 1

    def is_match_ethertype(self, value_to_check1, value_to_check2):
        """
        Passed a two prospective EtherTypes and check to
        see if they are the same.
        Return 1 for both the same EtherType and 0 for different
        Values can be hex or decimal and are 2 bytes in length
        """
        #*** Normalise any hex to decimal integers:
        if value_to_check1[:2] == '0x':
            #*** Looks like hex:
            try:
                value_to_check1_dec = int(value_to_check1, 16)
            except:
                exc_type, exc_value, exc_traceback = sys.exc_info()
                self.logger.error("error=E1000010 "
                        "Failed to convert hex to dec. Exception %s, %s, %s",
                            exc_type, exc_value, exc_traceback)
                return 0
        else:
            #*** Not hex:
            try:
                value_to_check1_dec = int(value_to_check1)
            except:
                exc_type, exc_value, exc_traceback = sys.exc_info()
                self.logger.error("error=E1000011 "
                        "Failed to convert to integer. Exception %s, %s, %s",
                            exc_type, exc_value, exc_traceback)
                return 0
        if value_to_check2[:2] == '0x':
            #*** Looks like hex:
            try:
                value_to_check2_dec = int(value_to_check2, 16)
            except:
                exc_type, exc_value, exc_traceback = sys.exc_info()
                self.logger.error("error=E1000012 "
                        "Failed to convert hex to dec. Exception %s, %s, %s",
                            exc_type, exc_value, exc_traceback)
                return 0
        else:
            #*** Not hex:
            try:
                value_to_check2_dec = int(value_to_check2)
            except:
                exc_type, exc_value, exc_traceback = sys.exc_info()
                self.logger.error("error=E1000013 "
                        "Failed to convert to integer. Exception %s, %s, %s",
                            exc_type, exc_value, exc_traceback)
                return 0
        if value_to_check1_dec == value_to_check2_dec:
            return 1
        else:
            return 0

    def is_match_ip_space(self, ip_addr, ip_space):
        """
        Passed an IP address and an IP address space and check
        if the IP address belongs to the IP address space.
        If it does return 1 otherwise return 0
        """
        #*** Does ip_space look like a CIDR network?:
        if "/" in ip_space:
            try:
                ip_space_object = IPNetwork(ip_space)
            except:
                exc_type, exc_value, exc_traceback = sys.exc_info()
                self.logger.error("error=E1000015 "
                        "Exception converting to IPNetwork object. "
                        "Exception %s, %s, %s",
                            exc_type, exc_value, exc_traceback)
                return 0
        #*** Does it look like an IP range?:
        elif "-" in ip_space:
            ip_range = ip_space.split("-")
            if len(ip_range) != 2:
                self.logger.error("error=E1000016 "
                    "Range split of ip_space %s on - was not len 2 but %s", 
                    ip_space, len(ip_range))
                return 0
            try:
                ip_space_object = list(iter_iprange(ip_range[0], ip_range[1]))
            except:
                exc_type, exc_value, exc_traceback = sys.exc_info()
                self.logger.error("error=E1000017 "
                        "Exception on conversion of %s to iter_iprange "
                        "Exception %s, %s, %s",
                        ip_range, exc_type, exc_value, exc_traceback)
                return 0
        else:
            #*** Or is it just a plain simple IP address?:
            try:
                ip_space_object = list(iter_iprange(ip_space, ip_space))
            except:
                exc_type, exc_value, exc_traceback = sys.exc_info()
                self.logger.error("error=E1000019 "
                        "Exception converting to IPAddress object. "
                        "Exception %s, %s, %s",
                            exc_type, exc_value, exc_traceback)
                return 0
        #*** Convert the IP address to a netaddr IPAddress object:
        try:
            ip_addr_object = IPAddress(ip_addr)
        except:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            self.logger.error("error=E1000021 "
                        "Exception converting to IPAddress object. "
                        "Exception %s, %s, %s",
                            exc_type, exc_value, exc_traceback)
            return 0
        #*** Now we have both in netaddr form, so do the match comparison:
        if ip_addr_object in ip_space_object:
            return 1
        else:
            return 0
