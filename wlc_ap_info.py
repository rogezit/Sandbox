from dnacentersdk import DNACenterAPI
import config
#import dna
from dna import get_devices_ids, readOnlyCommand
import pandas, time, re

ap_name = re.compile(r'AP\s+Name\s+:\s+(?P<ap_name>\S+)')
ap_statistics = re.compile(r'(?P<interface_name>\S+)\s+(?P<status>\S+)\s+(?P<speed>\d+\s\wbps)\s+(?P<duplex>\S+)\s+(?P<rx_packets>\d+)\s+(?P<tx_packets>\d+)\s+(?P<discarded_packets>\d+)')
ap_cdp_neighbors = re.compile(r'(?P<ap_name>\S+)\s+(?P<ap_ip>\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\s+(?P<neighbor_name>\S+)\s+(?P<neighbor_ip>\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\s+(?P<neighbor_port>\S+)')
ap_cdp_neighbors_wo_nip = re.compile(r'(?P<ap_name>\S+)\s+(?P<ap_ip>\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\s+(?P<neighbor_name>\S+)\s+(?!\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})(?P<neighbor_port>\S+)')
ap_cdp_neighbor_ip = re.compile(r'^(?P<neighbor_ip>\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})')

def get_ap_statistics_info(device_commands_dict):
    wlc_ap_dict = {}
    for device in device_commands_dict:
        command_lines = device_commands_dict[device]['show ap ethernet statistics'].split('\n')
        ap = ''
        ap_dict = {}
        for line in command_lines:
            if re.search(ap_name,line):
                ap = re.search(ap_name,line).group('ap_name')
            if re.search(ap_statistics,line):
                ap_stats = re.search(ap_statistics, line)
                ap_stats_dict = {}
                ap_stats_dict['interface'] = ap_stats.group('interface_name')
                ap_stats_dict['status'] = ap_stats.group('status')
                ap_stats_dict['speed'] = ap_stats.group('speed')
                ap_stats_dict['duplex'] = ap_stats.group('duplex')
                ap_stats_dict['rx_packets'] = ap_stats.group('rx_packets')
                ap_stats_dict['tx_packets'] = ap_stats.group('tx_packets')
                ap_stats_dict['discarded_packets'] = ap_stats.group('discarded_packets')
                ap_dict[ap] = ap_stats_dict
        wlc_ap_dict[device] = ap_dict
    return wlc_ap_dict

def get_ap_cdp_info(device_commands_dict):
    wlc_ap_dict = {}
    for device in device_commands_dict:
        command_lines = device_commands_dict[device]['show ap cdp neighbors'].split('\n')
        ap = ''
        ap_dict = {}
        for line in command_lines:
            if re.search(ap_cdp_neighbors,line):
                ap_neighbors = re.search(ap_cdp_neighbors, line)
                ap_stats_dict = {}
                ap_stats_dict['ap_ip'] = ap_neighbors.group('ap_ip')
                ap_stats_dict['neighbor_name'] = ap_neighbors.group('neighbor_name')
                ap_stats_dict['neighbor_ip'] = ap_neighbors.group('neighbor_ip')
                ap_stats_dict['neighbor_port'] = ap_neighbors.group('neighbor_port')
                ap_dict[ap_neighbors.group('ap_name')] = ap_stats_dict
            elif re.search(ap_cdp_neighbors_wo_nip,line):
                ap_neighbors = re.search(ap_cdp_neighbors_wo_nip, line)
                ap_stats_dict = {}
                ap_stats_dict['ap_ip'] = ap_neighbors.group('ap_ip')
                ap_stats_dict['neighbor_name'] = ap_neighbors.group('neighbor_name')
                ap_stats_dict['neighbor_port'] = ap_neighbors.group('neighbor_port')
                ap_dict[ap_neighbors.group('ap_name')] = ap_stats_dict
                ap = ap_neighbors.group('ap_name')
            elif re.search(ap_cdp_neighbor_ip,line):
                if not ap_dict[ap].get('neighbor_ip'):
                    ap_dict[ap]['neighbor_ip'] = re.search(ap_cdp_neighbor_ip,line).group('neighbor_ip')
        wlc_ap_dict[device] = ap_dict
    return wlc_ap_dict

if __name__ == '__main__':
    username = config.USERNAME
    password = config.PASSWORD
    url = config.URL
    print(username)
    print(password)
    print(url)
    dnac = DNACenterAPI(username=username,password=password,base_url=url,verify=False,wait_on_rate_limit=True)
    device_id_list = get_devices_ids(dnac,series='Cisco Catalyst 9800 Series Wireless Controllers')
    device_commands_dict = {}
    for device in device_id_list:
        command = readOnlyCommand(dnac,['show ap ethernet statistics','show ap cdp neighbors'], [device_id_list[device]])
        device_commands_dict.update(command)

    columns = ['Device', 'Show AP Ethernet Statistics']
    data = []
    for device in device_commands_dict:
        data.append([device,device_commands_dict[device]['show ap ethernet statistics']])
    dataframe = pandas.DataFrame(data, columns=columns)
    dataframe.to_excel(f'WLC_AP_Statistics_{time.strftime("%Y%m%d-%H%M%S")}.xlsx', index=False)

    ap_statistics = get_ap_statistics_info(device_commands_dict)
    ap_cdp_info = get_ap_cdp_info(device_commands_dict)

    with open(f'AP_CDP_Neighbors_{time.strftime("%Y%m%d-%H%M%S")}.csv', 'w') as ap_neighbors_file:
        print('AP Name, WLC, AP Interface, AP Speed, Neighbor Name, Neighbor IP, Neighbor Port', file=ap_neighbors_file)
        for wlc in ap_statistics:
            for ap in ap_statistics[wlc]:
                if ap_statistics[wlc][ap]['speed'].lower() == '100 mbps':
                    print(f'{ap},{wlc},{ap_statistics[wlc][ap]["interface"]},{ap_statistics[wlc][ap]["speed"]},{ap_cdp_info[wlc][ap]["neighbor_name"]},{ap_cdp_info[wlc][ap]["neighbor_ip"] if ap_cdp_info[wlc][ap].get("neighbor_ip") else ""},{ap_cdp_info[wlc][ap]["neighbor_port"]}', file=ap_neighbors_file)