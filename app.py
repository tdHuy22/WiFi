import subprocess
import time
import threading
from flask import Flask, render_template, request, redirect, url_for
import webbrowser

app = Flask(__name__)

WiFi_List = []
WPA_List = []

def check_internet_connection():
    try:
        print("Checking Internet Connection...")
        subprocess.check_output(['ping', '-c', '1', '8.8.8.8'], stderr=subprocess.STDOUT)
        return True
    except subprocess.CalledProcessError:
        print("No internet connection.")
        return False

def get_ip_address():
    try:
        result = subprocess.check_output(['hostname', '-I'])
        ip_address = result.decode('utf-8').strip().split()[0]
        return ip_address
    except Exception as e:
        print(f"Error getting IP address: {e}")
        return None

def turn_on_access_point():
    try:
        print("Turning on access point...")
        subprocess.run(['sudo', 'service', 'dhcpcd', 'stop'], check=True)
        subprocess.run(['sudo', 'service', 'NetworkManager', 'start'], check=True)
        # subprocess.run(['sudo', 'nmcli', 'device', 'wifi', 'hotspot', 'ifname', 'wlan0', 'con-name', 'UTK_Converter', 'ssid', 'RPI_Zero', 'password', 'RPI012345'], check=True)
        subprocess.run(['sudo', 'nmcli', 'device', 'connect', 'wlan0'], check=True)
        subprocess.run(['sudo', 'nmcli', 'connection', 'up', 'UTK_Converter'], check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error turning on access point: {e}")

def turn_off_access_point():
    try:
        print("Turning off access point...")
        subprocess.run(['sudo', 'nmcli', 'connection', 'down', 'UTK_Converter'], check=True)
        subprocess.run(['sudo', 'nmcli', 'device', 'disconnect', 'wlan0'], check=True)
        subprocess.run(['sudo', 'service', 'NetworkManager', 'stop'], check=True)
        subprocess.run(['sudo', 'service', 'dhcpcd', 'start'], check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error turning off access point: {e}")

def open_kiosk_mode(url):
    try:
        subprocess.Popen(['chromium-browser', '--kiosk', url])
    except Exception as e:
        print(f"Error opening Chrome in kiosk mode: {e}")

def continuous_internet_check():
    while True:
        if not check_internet_connection():
            turn_on_access_point()
        else:
            turn_off_access_point()
        time.sleep(60)  # Check every 60 seconds

@app.route('/')
def index():
    return render_template('index.html', WiFi_List=WiFi_List)

@app.route('/scan')
def scan():
    WiFi_List.clear()
    try:
        scan_output = subprocess.check_output(['sudo', 'iwlist', 'wlan0', 'scan']).decode('utf-8')
        lines = scan_output.split('\n')
        for line in lines:
            if 'ESSID' in line:
                wifi_name = line.split('"')[1]
                WiFi_List.append(wifi_name)
    except subprocess.CalledProcessError as e:
        print(f"Error scanning for Wi-Fi networks: {e}")
    
    return redirect(url_for('index'))

@app.route('/connect', methods=['POST'])
def connect():
    selected_wifi = request.form['wifi']
    password = request.form['password']
    turn_off_access_point()

    try:
        network_id = WPA_List.index(selected_wifi)
    except ValueError:
        network_id = None

    try:
        if network_id is not None:
            subprocess.run(['sudo', 'wpa_cli', '-i', 'wlan0', 'set_network', str(network_id), 'psk', f'"{password}"'], check=True)
        else:
            connect_output = subprocess.check_output(['sudo', 'wpa_cli', '-i', 'wlan0', 'add_network']).decode('utf-8')
            network_id = connect_output.strip()
            subprocess.run(['sudo', 'wpa_cli', '-i', 'wlan0', 'set_network', network_id, 'ssid', f'"{selected_wifi}"'], check=True)
            subprocess.run(['sudo', 'wpa_cli', '-i', 'wlan0', 'set_network', network_id, 'psk', f'"{password}"'], check=True)
            WPA_List.append(selected_wifi)
        
        subprocess.run(['sudo', 'wpa_cli', '-i', 'wlan0', 'enable_network', network_id], check=True)
        subprocess.run(['sudo', 'wpa_cli', '-i', 'wlan0', 'save_config'], check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error connecting to Wi-Fi network: {e}")
        turn_on_access_point()
        return redirect(url_for('index'))
    
    time.sleep(10)
    
    if check_internet_connection():
        print("Internet is connected.")
        open_kiosk_mode('https://192.168.1.5:8000/screen')
        return "Internet is connected"
    else:
        print("Failed to connect to the internet. Re-enabling access point.")
        turn_on_access_point()
        return redirect(url_for('index'))

if __name__ == '__main__':
    if check_internet_connection():
        print("Internet is connected.")
        open_kiosk_mode('https://192.168.1.5:8000/screen')
    else:
        turn_on_access_point()

    # Start continuous internet checking in a separate thread
    internet_check_thread = threading.Thread(target=continuous_internet_check)
    internet_check_thread.daemon = True
    internet_check_thread.start()

    app.run(host='0.0.0.0', port=5050, debug=True)
