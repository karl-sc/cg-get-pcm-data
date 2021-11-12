#!/usr/bin/env python
PROGRAM_NAME = "cg-get-pcm-data.py"
PROGRAM_DESCRIPTION = """
CloudGenix Get-PCM Throughput Script
---------------------------------------
Writes the past 7-days bandwidth average dailies and the 7-day average for each SPOKE site.
Output is placed in a CSV file
optional arguments:
  -h, --help            show this help message and exit
  --token "MYTOKEN", -t "MYTOKEN"
                        specify an authtoken to use for CloudGenix authentication
  --authtokenfile "MYTOKENFILE.TXT", -f "MYTOKENFILE.TXT"
                        a file containing the authtoken
  --csvfile csvfile, -c csvfile
                        the CSV Filename to write the BW averages to
  --days days, -d days  The number of days to average (default=1)
  --threshold threshold, -s threshold
                        The average threshold in decimal (default=.80 for 80 percent)
"""

####Library Imports
from cloudgenix import API, jd
import os
import sys
import argparse
from csv import reader


def parse_arguments():
    CLIARGS = {}
    parser = argparse.ArgumentParser(
        prog=PROGRAM_NAME,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=PROGRAM_DESCRIPTION
            )
    parser.add_argument('--token', '-t', metavar='"MYTOKEN"', type=str, 
                    help='specify an authtoken to use for CloudGenix authentication')
    parser.add_argument('--authtokenfile', '-f', metavar='"MYTOKENFILE.TXT"', type=str, 
                    help='a file containing the authtoken')
    parser.add_argument('--csvfile', '-c', metavar='csvfile', type=str, 
                    help='the CSV Filename to write the BW averages to', required=True)
    parser.add_argument('--days', '-d', metavar='days', type=int, 
                    help='The number of days to average (default=1)', required=False, default=1)
    parser.add_argument('--threshold', '-s', metavar='threshold', type=float, 
                    help='The average threshold in decimal (default=.80 for 80 percent)', required=False, default=.80)
    args = parser.parse_args()
    CLIARGS.update(vars(args))
    return CLIARGS

def authenticate(CLIARGS):
    print("AUTHENTICATING...")
    user_email = None
    user_password = None
    
    sdk = API()    
    ##First attempt to use an AuthTOKEN if defined
    if CLIARGS['token']:                    #Check if AuthToken is in the CLI ARG
        CLOUDGENIX_AUTH_TOKEN = CLIARGS['token']
        print("    ","Authenticating using Auth-Token in from CLI ARGS")
    elif CLIARGS['authtokenfile']:          #Next: Check if an AuthToken file is used
        tokenfile = open(CLIARGS['authtokenfile'])
        CLOUDGENIX_AUTH_TOKEN = tokenfile.read().strip()
        print("    ","Authenticating using Auth-token from file",CLIARGS['authtokenfile'])
    elif "X_AUTH_TOKEN" in os.environ:              #Next: Check if an AuthToken is defined in the OS as X_AUTH_TOKEN
        CLOUDGENIX_AUTH_TOKEN = os.environ.get('X_AUTH_TOKEN')
        print("    ","Authenticating using environment variable X_AUTH_TOKEN")
    elif "AUTH_TOKEN" in os.environ:                #Next: Check if an AuthToken is defined in the OS as AUTH_TOKEN
        CLOUDGENIX_AUTH_TOKEN = os.environ.get('AUTH_TOKEN')
        print("    ","Authenticating using environment variable AUTH_TOKEN")
    else:                                           #Next: If we are not using an AUTH TOKEN, set it to NULL        
        CLOUDGENIX_AUTH_TOKEN = None
        print("    ","Authenticating using interactive login")
    ##ATTEMPT AUTHENTICATION
    if CLOUDGENIX_AUTH_TOKEN:
        sdk.interactive.use_token(CLOUDGENIX_AUTH_TOKEN)
        if sdk.tenant_id is None:
            print("    ","ERROR: AUTH_TOKEN login failure, please check token.")
            sys.exit()
    else:
        while sdk.tenant_id is None:
            sdk.interactive.login(user_email, user_password)
            # clear after one failed login, force relogin.
            if not sdk.tenant_id:
                user_email = None
                user_password = None            
    print("    ","SUCCESS: Authentication Complete")
    return sdk

def logout(sdk):
    print("Logging out")
    sdk.get.logout()


def cgx_get_topology_list_by_site(sdk, site_id):
    topology_filter = '{"type":"basenet","nodes":["' +  site_id + '"]}'
    resp = sdk.post.topology(topology_filter)
    if resp.cgx_status:
        topology_list = resp.cgx_content.get("links", None)
        return topology_list
    else:
        return None

def cgx_average_series(metrics_series_structure, decimal_places=2):
    count = 0
    sum = 0
    for datapoints in metrics_series_structure.get("data",[{}])[0].get("datapoints",[{}]):
        if (datapoints.get("value",None) is not None):
            count += 1
            sum += datapoints.get("value",0)
    if count != 0:
        if decimal_places == 0:
            return round((sum/count))
        return round((sum/count),decimal_places)
    return 0

def cgx_get_wan_interfaces_by_site(sdk, site_id):
    wan_interfaces_resp = sdk.get.waninterfaces(site_id)
    wan_interfaces_list = wan_interfaces_resp.cgx_content.get("items")
    return wan_interfaces_list

def cgx_get_pcm_data_by_path_id(sdk, site_id, path_id, start_time, end_time):
    pcm_request = {"start_time":start_time,"end_time": end_time,
                    "interval":"5min","view":{"summary":False,"individual":"direction"},"filter":{"site":[ site_id ],"path":[ path_id ]},
                    "metrics":[{"name":"PathCapacity","statistics":["average"],"unit":"Mbps"}]
                    }
    pcm_resp = sdk.post.metrics_monitor(pcm_request)
    if pcm_resp.cgx_status:
        pcm_metric = pcm_resp.cgx_content.get("metrics", None)[0]['series']
        if pcm_metric[0]['view']['direction'] == 'Ingress':
            pcm_series_download = pcm_metric[0]
            pcm_series_upload = pcm_metric[1]
        else:
            pcm_series_download = pcm_metric[0]
            pcm_series_upload = pcm_metric[1]
        pcm_download_avg = cgx_average_series(pcm_series_download)
        pcm_upload_avg = cgx_average_series(pcm_series_upload)
        return(pcm_download_avg, pcm_upload_avg)

def cgx_get_internet_wan_by_site(sdk, site_id, start_time, end_time):
    topology_list   = cgx_get_topology_list_by_site(sdk, site_id)
    wan_interfaces_list = cgx_get_wan_interfaces_by_site(sdk, site_id)
    stub_count = 0
    return_array = []
    ### Get PCM Data
    for links in topology_list:
        if ((links['type'] == 'internet-stub') ):
            stub_count += 1
            (pcm_download_avg, pcm_upload_avg) = cgx_get_pcm_data_by_path_id(sdk, site_id, links['path_id'], start_time, end_time)
            ### Get CIR for PathID
            (cir_upload, cir_download) = (0, 0) ## Set default CIR to 0 in the event it is not found (this should not happen)
            for wan_int in wan_interfaces_list:
                if wan_int['id'] == links['path_id']:
                    cir_upload = wan_int['link_bw_up']
                    cir_download = wan_int['link_bw_down']
            #print("    Download", pcm_download_avg,"(MAX", cir_download,")   Upload",pcm_upload_avg,"(MAX", cir_upload,")")
            return_array.append( { 'pcm_download_avg': pcm_download_avg, 'download_configured':cir_download,
                                   'pcm_upload_avg'  : pcm_upload_avg, 'upload_configured':cir_upload,
                                   'circuit_name'    : links.get('target_circuit_name',"None"), 'circuit_network': links.get('network',"None"), 'link_status': links.get('status',"Unknown") } )
    return return_array


def write_2d_list_to_csv(csv_file, list_2d, write_mode="w"):
    import csv
    try:
        file = open(csv_file, write_mode)
        with file:    
            write = csv.writer(file)
            write.writerows(list_2d)
            return True
        return False
    except:
        return False



def cgx_generate_timestamps_days(days_interval=1, offset_days=0):
    from datetime import timedelta
    from datetime import datetime
    now = (datetime.utcnow() - timedelta(days=(offset_days)))
    end_time = now.isoformat()
    start_time = (now - timedelta(days=(days_interval))).isoformat() 
    return (str(start_time)+"Z", str(end_time)+"Z")

##########MAIN FUNCTION#############
def go(sdk, CLIARGS):
    try:
        site_list = sdk.get.sites().cgx_content.get("items")
    except:
        print("Error getting site list")
        return False
    days = CLIARGS['days']
    threshold = CLIARGS['threshold'] ## in Decimal, .9 = 90% of PCM
    csv_file = CLIARGS['csvfile']

    csv_array = []
    csv_array.append(["site_name", "site_id", "circuit_network", "circuit_name", "pcm_download_avg", "download_configured","download_deviation", "pcm_upload_avg", "upload_configured", "upload_deviation", "link_status","notes" ])
    counter = 0
    for site in site_list:
        counter += 1
        print("Iterating through site:",site['name'], "(", counter,"/",len(site_list),")")
        if (site['element_cluster_role'] == 'SPOKE'): ###ONLY Do Branches
            site_id = site['id']
            (start_time, end_time) = cgx_generate_timestamps_days(days_interval=1)
            pcm_data = cgx_get_internet_wan_by_site(sdk, site_id, start_time, end_time)
            for link in pcm_data:
                notes = ""
                site_name = site['name']
                site_id = site['id']
                circuit_network = link['circuit_network']
                circuit_name = link['circuit_name']
                pcm_download_avg = link['pcm_download_avg']
                download_configured = link['download_configured']
                pcm_upload_avg = link['pcm_upload_avg']
                upload_configured = link['upload_configured']
                link_status = link['link_status']
                if ( pcm_download_avg < (download_configured * threshold)): #If the PCM data is less than the configured CIR multiplied by our threshold (default .9 or 90%)
                    notes += "Download does not meet threshold "
                if ( pcm_upload_avg < (upload_configured * threshold)): #If the PCM data is less than the configured CIR multiplied by our threshold (default .9 or 90%)
                    notes += "Upload does not meet threshold"
                download_deviation = str(round( (pcm_download_avg/download_configured )*100,1   )) + "%"
                upload_deviation = str(round( (pcm_upload_avg/upload_configured )*100,1   )) + "%"
                csv_array.append([site_name, site_id, circuit_network, circuit_name, pcm_download_avg, download_configured,download_deviation, pcm_upload_avg, upload_configured, upload_deviation, link_status,notes ])

    result = write_2d_list_to_csv(csv_file, csv_array, write_mode="w")
    if result:
        print("Wrote CSV File",csv_file,"Successfully")
    else:
        print("Error writing file")

    



if __name__ == "__main__":
    ###Get the CLI Arguments
    CLIARGS = parse_arguments()
    
    ###Authenticate
    SDK = authenticate(CLIARGS)
    
    ###Run Code
    go(SDK, CLIARGS)

    ###Exit Program
    logout(SDK)


