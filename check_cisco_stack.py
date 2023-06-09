##!/usr/bin/python3
###############################################################
#  ========================= INFO ==============================
# NAME:         check_cisco_stack.py
# AUTHOR:       Jeffrey Wolak
# LICENSE:      MIT
# ======================= SUMMARY ============================
# Python rewrite of check_snmp_cisco_stack.pl
#
# https://exchange.nagios.org/directory/Plugins/Hardware/Network-Gear/Cisco/Check-cisco-3750-stack-status/details
#
# It looks like the perl version wasn't maintained and had some
# bugs working with newer switch models
#
# =================== SUPPORTED DEVICES =======================
# Lab testing with:
# 3750G
# 3750X
# 3850X
#
# !!! WARNING !!!
# See relevant bug reports before using in your environment
#
# Bug CSCsg18188 - Major
# Desc: May cause memory leak
# Effects: 12.2(25)SEE1
# Fixed: 12.2(35)SE
#
# Bug CSCse53528 - Minor
# Desc: May report the wrong status
# Effects: 12.2(25)SEE
# Fixed: 12.2(25)SEE3, 12.2(35)SE (and Later)
#
# ========================= NOTES =============================
# 11-27-2015: Version 1.0 released (Moving to PROD)
# 12-04-2015: Now marking all states other than "ready" as critical
# TODO: Add SNMP version 2 support
#
# ======================= LICENSE =============================
#
# MIT License
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
# LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
# WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
#
# ###############################################################
import collections

from easysnmp import Session  # Requires easysnmp compiled with python bindings
import sys       # exit
import getopt    # for parsing options
import logging   # for debug option

# https://docs.python.org/3/howto/argparse.html
# https://docs.python.org/3/library/argparse.html#module-argparse
import argparse  # for parsing options

# Global program variables
__program_name__ = 'Cisco Stack'
__version__ = 1.1


###############################################################
#
# Exit codes and status messages
#
###############################################################
OK = 0
WARNING = 1
CRITICAL = 2
UNKNOWN = 3


def exit_status(x):
    return {
        0: 'OK',
        1: 'WARNING',
        2: 'CRITICAL',
        3: 'UNKNOWN'
    }.get(x, 'UNKNOWN')


###############################################################
#
# usage() - Prints out the usage and options help
#
###############################################################
def usage():
    print ("""
\t-h --help\t\t- Prints out this help message
\t-v --version\t\t- Prints the version number
\t-H --host <ip_address>\t- IP address of the cisco stack
\t-c --community <string>\t- SNMP community string
\t-d --debug\t\t- Verbose mode for debugging
""")
    sys.exit(UNKNOWN)


###############################################################
#
# parse_args() - parses command line args and returns options dict
#
###############################################################
parser = argparse.ArgumentParser()

#parser.add_argument("-h", "--help", dest='help', default='pass', help="User password")
#parser.add_argument('--cmd', dest='cmd', help="Command to run")
parser.add_argument("-H", "--host", dest="host", required=True,
                    help="- IP address of the cisco stack")
parser.add_argument("-c", "--community", dest="community", default="Public",
                    help="- SNMP community string")
parser.add_argument("-d", "--debug", action="store_true")
parser.add_argument("-v", "--version", action="store_true")

subparser_particular = parser.add_subparsers(title='switch subcommands',
                                   description='particular switch number subcommands',
                                   help='part --help for more details',
                                   dest='subparser_name')
parser_particular = subparser_particular.add_parser('part', aliases=['particular', 'partial'])
parser_particular.add_argument('-S', '--switchnumbers',
                               dest='switchnumbers',
                               choices=range(1, 9),
                               required=True,
                               action='extend',
                               nargs='+',
                               type=int,
                               help='- Switch number(s) in stack, range from 1 to 8')

parser_particular.add_argument('-E', '--expectedstate',
                               dest='expectedstate',
                               choices=range(1, 11),
                               required=True,
                               action='extend',
                               nargs='+',
                               type=int,
                               help='- Expected status of the switch number(s) accordingly, from 1 to 12')

parser_particular.add_argument('-T', '-test', dest='test', action='store_true',
                               help='- Data for testing')
parser_particular.add_argument('-tS', '--tswitchnumbers',
                               dest='tswitchnumbers',
                               choices=range(1, 9),
                               action='extend',
                               nargs='+',
                               type=int,
                               help='- Switch number(s) in stack, range from 1 to 8')
parser_particular.add_argument('-tE', '--texpectedstate',
                               dest='texpectedstate',
                               choices=range(1, 11),
                               action='extend',
                               nargs='+',
                               type=int,
                               help='- Expected status of the switch number(s) accordingly, from 1 to 12')
#parser.add_argument('--cmd', dest='cmd', help="Command to run")
#parser.add_argument('--ipfile', dest='ipfile', help="Command to get files with IPs")
#parser.add_argument('--host', dest='host', default='localhost', help='Host to connect to')
#parser.add_argument('--port', dest='port', default=22, help="Port to connect on", type=int)
#parser.add_argument('-u', dest='user', default='user', help="User name to authenticate as")
#parser.add_argument('--tftp', dest='tftp', default='10.35.0.106', help="tftp server address")


def parse_args():
    options = dict([
        ('remote_ip', None),
        ('community', 'Public'),
    ])
    try:
        opts, args = getopt.getopt(sys.argv[1:], "hvH:c:d", ["help", "host=", "version", "community=", "debug"])
    except getopt.GetoptError(err):
        # print help information and exit:
        print (str(err))    # will print something like "option -a not recognized"
        usage()
    for o, a in opts:
        if o in ("-d", "--debug"):
            logging.basicConfig(
                level=logging.DEBUG,
                format='%(asctime)s - %(funcName)s - %(message)s'
            )
            logging.debug('*** Debug mode started ***')
        elif o in ("-v", "--version"):
            print ("{0} plugin version {1}".format(__program_name__, __version__))
            sys.exit(0)
        elif o in ("-h", "--help"):
            usage()
        elif o in ("-H", "--host"):
            options['remote_ip'] = a
        elif o in ("-c", "--community"):
            options['community'] = a
        else:
            assert False, "unhandled option"
    logging.debug('Printing initial variables')
    logging.debug('remote_ip: {0}'.format(options['remote_ip']))
    logging.debug('community: {0}'.format(options['community']))
    if options['remote_ip'] is None:
        print("Requires host to check")
        usage()
    return options


###############################################################
#
# plugin_exit() - Prints value and exits
# :param exitcode: Numerical or constant value
# :param message: Message to print
#
###############################################################
def plugin_exit(exitcode, message=''):
    logging.debug('Exiting with status {0}. Message: {1}'.format(exitcode, message))
    status = exit_status(exitcode)
    print('{0} {1} - {2}'.format(__program_name__, status, message))
    sys.exit(exitcode)


###############################################################
#
# get_stack_info() - Acquire info about the stack status
# :param remote_ip: IP address of the system
# :param community: SNMP read community
# :return member_table: dict of dict of stack status
#
# -- member_table example:
# {'4001': {'status': 'ready', 'index': '4001', 'number': '4', 'status_num': '4'},
#  '2001': {'status': 'ready', 'index': '2001', 'number': '2', 'status_num': '4'},
#  '3001': {'status': 'ready', 'index': '3001', 'number': '3', 'status_num': '4'},
#  '1001': {'status': 'ready', 'index': '1001', 'number': '1', 'status_num': '4'}}
#
# -- OID definitions:
# OID: 1.3.6.1.4.1.9.9.500.1.2.1.1.1
#   "This object contains the current switch identification number.
#   This number should match any logical labeling on the switch.
#   For example, a switch whose interfaces are labeled
#   'interface #3' this value should be 3."
#
# OID: 1.3.6.1.4.1.9.9.500.1.2.1.1.6
#   "The current state of a switch"
#   See stack_state() documentation for all states
#
###############################################################
def get_stack_info(remote_ip, community):
    member_table = {}
    session = Session(hostname=remote_ip, community=community, version=2)
    stack_table_oid = session.bulkwalk('.1.3.6.1.4.1.9.9.500.1.2.1.1.1')
    logging.debug('Walking stack table -- ')
    if not stack_table_oid:
        plugin_exit(CRITICAL, 'Unable to retrieve SNMP stack table')
    for member in stack_table_oid:
        logging.debug('Member info: {0}'.format(member))
        a = {'number': member.value, 'index': member.oid.rsplit('.').pop()}
        member_table[a['index']] = a
    stack_status_oid = session.bulkwalk(oids='.1.3.6.1.4.1.9.9.500.1.2.1.1.6')
    logging.debug('Walking stack status -- ')
    if not stack_status_oid:
        plugin_exit(CRITICAL, 'Unable to retrieve SNMP stack status')
    for member in stack_status_oid:
        logging.debug('Member info: {0}'.format(member.value))
        index = member.oid.rsplit('.').pop()
        member_table[index]['status_num'] = member.value
        member_table[index]['status'] = stack_state(member.value)
    logging.debug('Stack info table to return: {0}'.format(member_table))
    return member_table


# -- STACK STATES --
#
# Defined by Cisco:
#
# http://tools.cisco.com/Support/SNMP/do/BrowseOID.do?
#   objectInput=1.3.6.1.4.1.9.9.500.1.2.1.1.6&translate=Translate&submitValue=SUBMIT
#
#
# "The current state of a switch:
#
# waiting - Waiting for a limited time on other
# switches in the stack to come online.
#
# progressing - Master election or mismatch checks in
# progress.
#
# added - The switch is added to the stack.
#
# ready - The switch is operational.
#
# sdmMismatch - The SDM template configured on the master
# is not supported by the new member.
#
# verMismatch - The operating system version running on the
# master is different from the operating
# system version running on this member.
#
# featureMismatch - Some of the features configured on the
# master are not supported on this member.
#
# newMasterInit - Waiting for the new master to finish
# initialization after master switchover
# (Master Re-Init).
#
# provisioned - The switch is not an active member of the
# stack.
#
# invalid - The switch's state machine is in an
# invalid state.
#
# removed - The switch is removed from the stack."

def stack_state(x):
    return {
        '1': 'waiting',
        '2': 'progressing',
        '3': 'added',
        '4': 'ready',
        '5': 'sdmMismatch',
        '6': 'verMismatch',
        '7': 'featureMismatch',
        '8': 'newMasterInit',
        '9': 'provisioned',
        '10': 'invalid',
        '11': 'removed',
    }.get(x, 'UNKNOWN')


###############################################################
#
# get_ring_status() - Acquire info about the stack status
# :param remote_ip: IP address of the system
# :param community: SNMP read community
# :return stack_ring_status: status of the stack ring
#
# OID: 1.3.6.1.4.1.9.9.500.1.1.3
#   "A value of 'true' is returned when the stackports are
#   connected in such a way that it forms a redundant ring."
#
###############################################################
def get_ring_status(remote_ip, community):
    session = Session(hostname=remote_ip, community=community, version=2)
    ring_status_oid = session.get('.1.3.6.1.4.1.9.9.500.1.1.3.0')
    logging.debug('Getting stack ring redundancy status -- ')
    if not ring_status_oid:
        plugin_exit(CRITICAL, 'Unable to retrieve SNMP ring status')
    logging.debug('Ring status: {0}'.format(ring_status_oid.value))
    stack_ring_status = ring_status_oid.value
    return stack_ring_status


###############################################################
#
# evaluate_results() - Evaluate status of stack and ring
# :param stack: stack info dict
# :param ring: ring status
# :return result: result for exit code
# :return message: status message string for exit
#
###############################################################
def evaluate_results(stack, ring):
    message = ["Members: "]
    result = OK
    logging.debug('Checking each stack member')
    for i, member in iter(stack.items()):
        logging.debug('Member {0} is {1}'.format(member['number'], member['status']))
        message.append("{0}: {1}, ".format(member['number'], member['status']))
        if member['status_num'] != '4':
            result = CRITICAL
            logging.debug('Status changed to CRITICAL')
    if ring == '1':
        message.append("Stack Ring is redundant")
    else:
        message.append("Stack Ring is non-redundant")
        if result == OK:
            result = WARNING
            logging.debug('Status changed to WARNING')
    message = ''.join(message)
    return result, message

###############################################################
#
# get_part_status() - get_part_status function
#
###############################################################
def get_part_status(switchnumbers, expectedstate):

    return 0

###############################################################
#
# get_part_status() - get_part_status function
#
###############################################################
def get_part_status_test(switchnumbers, expectedstate, tswitchnumbers, texpectedstate):
    print("switchnumbers " + ' '.join(str(x) for x in switchnumbers))
    print("expectedstate " + ' '.join(str(x) for x in expectedstate))
    print("tswitchnumbers " + ' '.join(str(x) for x in tswitchnumbers))
    print("texpectedstate " + ' '.join(str(x) for x in texpectedstate))
    if (switchnumbers == tswitchnumbers):
        print("1st is equal")
    else:
        print("1st is not equal")

    if (expectedstate == texpectedstate):
        print("2nd is equal")
    else:
        print("2nd is not equal")

    switeches_dict = dict(zip(switchnumbers, expectedstate))
    print(str(switeches_dict))

    tswiteches_dict = dict(zip(tswitchnumbers, texpectedstate))
    print(str(tswiteches_dict))

    if (switeches_dict == tswiteches_dict):
        print("The dicts are equal")
    else:
        print("The dicts are not equal")

    return 0

###############################################################
#
# main() - Main function
#
###############################################################
def main():
    #print("test")
    args = parser.parse_args()
    options = parse_args()
    if args.subparser_name == 'part':
        if args.test:
            part_result = get_part_status_test(args.switchnumbers, args.expectedstate,
                                               args.tswitchnumbers, args.texpectedstate)
        else:
            part_result = get_part_status(args.switchnumbers, args.expectedstate)
    else:
        stack = get_stack_info(args.host, args.community)
        ring = get_ring_status(args.host, args.community)

    result, message = evaluate_results(stack, ring)
    plugin_exit(result, message)
    print(args)


if __name__ == "__main__":
    main()
