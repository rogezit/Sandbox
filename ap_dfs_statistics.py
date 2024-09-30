import csv,json
from dnacentersdk import DNACenterAPI
import time, re
#from config import URL
import config

ap_name_regex = re.compile(r'^AP\sName\s+:\s+(?P<ap_name>\S+)')
channel_changes_regex = re.compile(r'^\s+Channel\schanges\sdue\sto\sradar\s+:\s+(?P<channel_changes>\d+)')
filtered_events_on_serving_radio_regex = re.compile(r'^\s+Filtered\sevents\son\sserving\sradio\s+:\s+(?P<filtered_on_radio>\d+)')
filtered_events_on_integrated_rf_regex = re.compile(r'^\s+Filtered\sevents\son\sCisco\sIntegrated\sRF\sASIC\s+:\s+(?P<filtered_on_integrted_rf>\d+)')
triggered_radar_events_regex = re.compile(r'^\s+Triggered\sradar\sevents\s+:\s+(?P<triggered_radar_events>\d+)')
dfs_statistics_last_update_regex = re.compile(r'^\s+DFS\sstatistics\slast\supdated\s+:\s+(?P<dfs_statistics_updated>.+)')

def get_ap_dfs_statistics(dnac,device_commands_dict):
    wlc_ap_dict = {}
    for wlc in device_commands_dict:
        wlc_details = dnac.devices.get_device_list(hostname=wlc)
        wlc_software = wlc_details['response'][0]['softwareType']
        wlc_software_version = wlc_details['response'][0]['softwareVersion']
        command_lines = device_commands_dict[wlc]['show ap auto-rf dot11 5ghz'].split('\n')
        wlc_ap_dict[wlc] = {}
        wlc_ap_dict[wlc]['software_type'] = wlc_software
        wlc_ap_dict[wlc]['software_version'] = wlc_software_version
        wlc_ap_dict[wlc]['ap'] = {}
        for line in command_lines:
            if re.search(ap_name_regex, line):
                ap_name = re.search(ap_name_regex, line).group('ap_name')
                if wlc_ap_dict[wlc]['ap'].get(ap_name):
                    ap_number = len(wlc_ap_dict[wlc]['ap'][ap_name])
                    wlc_ap_dict[wlc]['ap'][ap_name].append({'channel_changes': 'NA',
                                                   'filtered_events_on_serving_radio': 'NA',
                                                   'filtered_events_on_integrated_rf': 'NA',
                                                   'triggered_radar_events': 'NA',
                                                   'dfs_statistics_last_update': 'NA'})
                else:
                    wlc_ap_dict[wlc]['ap'][ap_name] = []
                    ap_number = 0
                    wlc_ap_dict[wlc]['ap'][ap_name].append({'channel_changes': 'NA',
                                                   'filtered_events_on_serving_radio': 'NA',
                                                   'filtered_events_on_integrated_rf': 'NA',
                                                   'triggered_radar_events': 'NA',
                                                   'dfs_statistics_last_update': 'NA'})
            elif re.search(channel_changes_regex, line):
                channel_changes = re.search(channel_changes_regex, line).group('channel_changes')
                wlc_ap_dict[wlc]['ap'][ap_name][ap_number]['channel_changes'] = channel_changes
            elif re.search(filtered_events_on_serving_radio_regex, line):
                filtered_events_on_serving_radio = re.search(filtered_events_on_serving_radio_regex, line).group('filtered_on_radio')
                wlc_ap_dict[wlc]['ap'][ap_name][ap_number]['filtered_events_on_serving_radio'] = filtered_events_on_serving_radio
            elif re.search(filtered_events_on_integrated_rf_regex, line):
                filtered_events_on_integrated_rf = re.search(filtered_events_on_integrated_rf_regex, line).group('filtered_on_integrted_rf')
                wlc_ap_dict[wlc]['ap'][ap_name][ap_number]['filtered_events_on_integrated_rf'] = filtered_events_on_integrated_rf
            elif re.search(triggered_radar_events_regex, line):
                triggered_radar_events = re.search(triggered_radar_events_regex, line).group('triggered_radar_events')
                wlc_ap_dict[wlc]['ap'][ap_name][ap_number]['triggered_radar_events'] = triggered_radar_events
            elif re.search(dfs_statistics_last_update_regex, line):
                dfs_statistics_last_update = re.search(dfs_statistics_last_update_regex, line).group('dfs_statistics_updated')
                wlc_ap_dict[wlc]['ap'][ap_name][ap_number]['dfs_statistics_last_update'] = dfs_statistics_last_update
    return wlc_ap_dict

def get_devices_ids(dnac,series=None,family=None,in_name=None):
    device_ids = {}
    if series or family:
        offset = 1
        if series:
            devices = dnac.devices.get_device_list(series=series, limit=500, offset=offset)
        elif family:
            devices = dnac.devices.get_device_list(family=family, limit=500, offset=offset)
        while devices.response:
            for device in devices.response:
                if in_name:
                    if any(name in device['hostname'] for name in in_name):
                        device_ids[device['hostname']] = device['id']
                else:
                    device_ids[device['hostname']] = device['id']
            offset = offset + 500
            if series:
                devices = dnac.devices.get_device_list(series=series, limit=500, offset=offset)
            elif family:
                devices = dnac.devices.get_device_list(family=family, limit=500, offset=offset)
        return(device_ids)

def readOnlyCommand(dnac, commands, deviceList, log_file=None):
    device_commands_dict = {}
    log_file_name = log_file if log_file else f'command_runner_status_{time.strftime("%d%b%Y_%H%M")}.csv'
    with open(log_file_name, 'a', newline='') as status_write:
        status_writer = csv.writer(status_write)
        print("Executing command on devices...")
        i = 0
        for device_id in deviceList:
            command_dict = {}
            i += 1
            output = []
            status = []
            for x in range(0,len(commands),5):
                five_commands = commands[x:x+5]
                reexcecute = True
                while reexcecute:
                    try:
                        cli = dnac.command_runner.run_read_only_commands_on_devices(commands=five_commands,deviceUuids=[device_id])
                        task = dnac.task.get_task_by_id(cli.response.taskId)
                        while task.response.progress == 'CLI Runner request creation':
                            time.sleep(5)
                            task = dnac.task.get_task_by_id(cli.response.taskId)
                        fileId = json.loads(task.response.progress)['fileId']
                        file = dnac.file.download_a_file_by_fileid(fileId)
                        clioutput = json.loads(file.data.decode('utf-8'))
                        reexcecute = False
                    except UnicodeDecodeError:
                        reexcecute = True
                    except:
                        hostname = dnac.devices.get_device_by_id(device_id)
                        print(f'Command execution failed on device {hostname["response"]["hostname"]}. Please validate the device status.')
                        status_writer.writerow([f'{hostname["response"]["hostname"]}','Command execution failed. Validate the device stauts.'])
                        reexcecute = False
                        clioutput = []
                        for command in five_commands:
                            command_dict[command] = 'Command execution fail.'
                try:
                    for device in clioutput:
                        hostname = dnac.devices.get_device_by_id(device['deviceUuid'])
                        for command in five_commands:
                            if device['commandResponses']['SUCCESS'] and device['commandResponses']['SUCCESS'].get(command):
                                output.append(device['commandResponses']['SUCCESS'][command])
                                command_dict[command] = device['commandResponses']['SUCCESS'][command]
                                status.append(f'Command {command} execution success.')
                            else:
                                output.append('Command execution fail.')
                                command_dict[command] = 'Command execution fail.'
                                if device['commandResponses']['FAILURE'] and device['commandResponses']['FAILURE'].get(command):
                                    status.append(device['commandResponses']['FAILURE'][command])
                                elif device['commandResponses']['BLACKLISTED'] and device['commandResponses']['BLACKLISTED'].get(command):
                                    status.append(device['commandResponses']['BLACKLISTED'][command])
                                else:
                                    status.append(f'Command {command} execution fail.')
                except:
                    print()
            device_commands_dict[hostname['response']['hostname']] = command_dict
    return device_commands_dict

if __name__ == '__main__':
    #username = input('Enter DNAC username: ')
    #password = input('Enter DNAC password: ')
    #url = input('Enter DNAC URL: ')
    username = config.USERNAME
    password = config.PASSWORD
    url = config.URL
    print(username)
    print(password)
    print(url)
    dnac = DNACenterAPI(username=username,password=password,base_url=url,verify=False,wait_on_rate_limit=True)
    device_id_list = get_devices_ids(dnac,series='Cisco Catalyst 9800 Series Wireless Controllers')
    device_commands_dict = {}
    i = 0
    current_time_date = time.strftime("%Y%m%d-%H%M%S")
    log_file = f'command_runner_errors_{current_time_date}.csv'
    with open(log_file, 'w'):
        pass
    for device in device_id_list:
        i += 1
        print(f'Device {i}/{len(device_id_list)} - {device}')
        command = readOnlyCommand(dnac,['show ap auto-rf dot11 5ghz'], [device_id_list[device]],log_file=log_file)
        device_commands_dict.update(command)
    ap_dfs_statistics = get_ap_dfs_statistics(dnac,device_commands_dict)

    with open(f'AP_DFS_Statistics_{current_time_date}.csv', 'w') as ap_dfs_statistics_file:
        print('AP Name,WLC,WLCSoftware Type,WLC Software Version,Channel changes due to radar,Filtered events on serving radio,Filtered events on Cisco Integrated RF ASIC,Triggered radar events,DFS statistics last updated', file=ap_dfs_statistics_file)
        for wlc in ap_dfs_statistics:
            for ap in ap_dfs_statistics[wlc]['ap']:
                for ap_stats in ap_dfs_statistics[wlc]['ap'][ap]:
                     print(f'{ap},{wlc},{ap_dfs_statistics[wlc]["software_type"]},{ap_dfs_statistics[wlc]["software_version"]},{ap_stats["channel_changes"]},{ap_stats["filtered_events_on_serving_radio"]},{ap_stats["filtered_events_on_integrated_rf"]},{ap_stats["triggered_radar_events"]},{ap_stats["dfs_statistics_last_update"]}',file=ap_dfs_statistics_file)
                    #print(f'{ap},{wlc},{ap_dfs_statistics[wlc]["software_type"]},{ap_dfs_statistics[wlc]["software_version"]},{ap_dfs_statistics[wlc]["ap"][ap]["channel_changes"]},{ap_dfs_statistics[wlc]["ap"][ap]["filtered_events_on_serving_radio"]},{ap_dfs_statistics[wlc]["ap"][ap]["filtered_events_on_integrated_rf"]},{ap_dfs_statistics[wlc]["ap"][ap]["triggered_radar_events"]},{ap_dfs_statistics[wlc]["ap"][ap]["dfs_statistics_last_update"]}',file=ap_dfs_statistics_file)
