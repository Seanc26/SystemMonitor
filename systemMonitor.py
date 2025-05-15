#!/usr/bin/env python3

import psutil
import time
import os
import signal
import sys
import threading
import platform
import socket
from datetime import datetime, timedelta
from collections import deque

class Colors:
    RESET = '\033[0m'
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    BOLD = '\033[1m'

class NetworkStats:
    def __init__(self):
        self.upload = 0
        self.download = 0
        self.lock = threading.Lock()
        self.running = True
        self.thread = threading.Thread(target=self._update_network_stats)
        self.thread.daemon = True
        self.thread.start()

    def _update_network_stats(self):
        last_net_io = psutil.net_io_counters()
        last_time = time.time()
        
        while self.running:
            time.sleep(0.5)
            current_net_io = psutil.net_io_counters()
            current_time = time.time()
            
            time_diff = current_time - last_time
            if time_diff > 0:
                with self.lock:
                    self.upload = (current_net_io.bytes_sent - last_net_io.bytes_sent) / time_diff / 1024
                    self.download = (current_net_io.bytes_recv - last_net_io.bytes_recv) / time_diff / 1024
                
                last_net_io = current_net_io
                last_time = current_time

    def get_stats(self):
        with self.lock:
            return self.upload, self.download

    def stop(self):
        self.running = False
        self.thread.join()

class DiskIOStats:
    def __init__(self):
        self.read_bytes = 0
        self.write_bytes = 0
        self.lock = threading.Lock()
        self.running = True
        self.thread = threading.Thread(target=self._update_disk_stats)
        self.thread.daemon = True
        self.thread.start()

    def _update_disk_stats(self):
        last_disk_io = psutil.disk_io_counters()
        last_time = time.time()
        
        while self.running:
            time.sleep(0.5)
            current_disk_io = psutil.disk_io_counters()
            current_time = time.time()
            
            time_diff = current_time - last_time
            if time_diff > 0 and last_disk_io:
                with self.lock:
                    self.read_bytes = (current_disk_io.read_bytes - last_disk_io.read_bytes) / time_diff
                    self.write_bytes = (current_disk_io.write_bytes - last_disk_io.write_bytes) / time_diff
                
                last_disk_io = current_disk_io
                last_time = current_time

    def get_stats(self):
        with self.lock:
            return self.read_bytes, self.write_bytes

    def stop(self):
        self.running = False
        self.thread.join()

def move_cursor_top():
    print('\033[H', end='')

def hide_cursor():
    print('\033[?25l', end='')

def show_cursor():
    print('\033[?25h', end='')

def setup_screen():
    print('\033[2J\033[H', end='')
    hide_cursor()

def get_size(bytes):
    for unit in ['', 'K', 'M', 'G', 'T', 'P']:
        if bytes < 1024:
            return f"{bytes:.2f}{unit}B"
        bytes /= 1024

def get_cpu_temp():
    try:
        temps = psutil.sensors_temperatures()
        if 'coretemp' in temps:
            return sum(temp.current for temp in temps['coretemp']) / len(temps['coretemp'])
        return None
    except:
        return None

def get_battery():
    try:
        battery = psutil.sensors_battery()
        if battery:
            return battery.percent, battery.power_plugged
        return None, None
    except:
        return None, None

def get_cpu_freq():
    try:
        freq = psutil.cpu_freq()
        return freq.current if freq else None
    except:
        return None

def get_uptime():
    return timedelta(seconds=int(time.time() - psutil.boot_time()))

def get_gpu_info():
    try:
        import GPUtil
        gpus = GPUtil.getGPUs()
        if gpus:
            return [(gpu.name, gpu.temperature, gpu.load * 100, gpu.memoryUsed, gpu.memoryTotal) 
                   for gpu in gpus]
        return None
    except:
        return None

def get_network_interfaces():
    interfaces = []
    for interface, stats in psutil.net_if_stats().items():
        if stats.isup:
            try:
                addrs = psutil.net_if_addrs()[interface]
                for addr in addrs:
                    if addr.family == socket.AF_INET:
                        interfaces.append((interface, addr.address))
                        break
            except:
                continue
    return interfaces

def get_top_processes():
    processes = []
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            pinfo = proc.info
            pinfo['cpu_times'] = proc.cpu_times()
            processes.append(pinfo)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    
    for proc_info in processes:
        try:
            proc = psutil.Process(proc_info['pid'])
            new_cpu_times = proc.cpu_times()
            cpu_percent = (new_cpu_times.user + new_cpu_times.system - 
                         proc_info['cpu_times'].user - proc_info['cpu_times'].system) * 100
            proc_info['cpu_percent'] = cpu_percent
            proc_info['memory_percent'] = proc.memory_percent()
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            proc_info['cpu_percent'] = 0
            proc_info['memory_percent'] = 0
    
    return sorted(processes, key=lambda p: p['cpu_percent'], reverse=True)[:5]

def colorize(value, thresholds):
    if value >= thresholds[1]:
        return f"{Colors.RED}{value:.1f}%{Colors.RESET}"
    elif value >= thresholds[0]:
        return f"{Colors.YELLOW}{value:.1f}%{Colors.RESET}"
    return f"{Colors.GREEN}{value:.1f}%{Colors.RESET}"

def print_system_info(network_stats, disk_stats):
    move_cursor_top()
    
    print(f"{Colors.BOLD}System Monitor{Colors.RESET}")
    print("-" * 50)
    
    hostname = socket.gethostname()
    os_info = f"{platform.system()} {platform.release()}"
    print(f"Hostname: {Colors.CYAN}{hostname}{Colors.RESET}")
    print(f"OS: {Colors.CYAN}{os_info}{Colors.RESET}")
    print("-" * 50)
    
    uptime = get_uptime()
    print(f"Uptime: {uptime}")
    print("-" * 50)
    
    cpu_percent = psutil.cpu_percent(interval=0)
    cpu_freq = get_cpu_freq()
    cpu_temp = get_cpu_temp()
    load_avg = os.getloadavg()
    
    print(f"CPU Usage: {colorize(cpu_percent, [70, 90])}")
    print(f"System Load: {Colors.CYAN}{load_avg[0]:.2f}, {load_avg[1]:.2f}, {load_avg[2]:.2f}{Colors.RESET}")
    if cpu_freq:
        print(f"CPU Frequency: {cpu_freq:.0f} MHz")
    if cpu_temp:
        temp_color = Colors.RED if cpu_temp > 80 else Colors.YELLOW if cpu_temp > 60 else Colors.GREEN
        print(f"CPU Temperature: {temp_color}{cpu_temp:.1f}°C{Colors.RESET}")
    print("-" * 50)

    memory = psutil.virtual_memory()
    swap = psutil.swap_memory()
    print(f"RAM Usage: {colorize(memory.percent, [70, 90])}")
    print(f"RAM Used/Total: {get_size(memory.used)} / {get_size(memory.total)}")
    print(f"Swap Usage: {colorize(swap.percent, [70, 90])}")
    print(f"Swap Used/Total: {get_size(swap.used)} / {get_size(swap.total)}")
    print("-" * 50)

    gpu_info = get_gpu_info()
    if gpu_info:
        print(f"{Colors.BOLD}GPU Information:{Colors.RESET}")
        for name, temp, load, mem_used, mem_total in gpu_info:
            print(f"GPU: {Colors.CYAN}{name}{Colors.RESET}")
            temp_color = Colors.RED if temp > 80 else Colors.YELLOW if temp > 60 else Colors.GREEN
            print(f"Temperature: {temp_color}{temp}°C{Colors.RESET}")
            print(f"Load: {colorize(load, [70, 90])}")
            print(f"Memory: {get_size(mem_used)} / {get_size(mem_total)}")
        print("-" * 50)

    battery_percent, power_plugged = get_battery()
    if battery_percent is not None:
        battery_color = Colors.RED if battery_percent < 20 else Colors.YELLOW if battery_percent < 50 else Colors.GREEN
        status = "Charging" if power_plugged else "Discharging"
        print(f"Battery: {battery_color}{battery_percent}%{Colors.RESET} ({status})")
        print("-" * 50)

    upload, download = network_stats.get_stats()
    print(f"Network Usage:")
    print(f"Upload: {Colors.CYAN}{upload:.1f} KB/s{Colors.RESET}")
    print(f"Download: {Colors.CYAN}{download:.1f} KB/s{Colors.RESET}")
    
    interfaces = get_network_interfaces()
    if interfaces:
        print("\nNetwork Interfaces:")
        for interface, ip in interfaces:
            print(f"{interface}: {Colors.CYAN}{ip}{Colors.RESET}")
    print("-" * 50)

    read_bytes, write_bytes = disk_stats.get_stats()
    print(f"Disk I/O:")
    print(f"Read: {Colors.CYAN}{get_size(read_bytes)}/s{Colors.RESET}")
    print(f"Write: {Colors.CYAN}{get_size(write_bytes)}/s{Colors.RESET}")
    print("-" * 50)

    print(f"{Colors.BOLD}Top 5 Processes by CPU Usage:{Colors.RESET}")
    print(f"{'PID':<8} {'Name':<20} {'CPU %':<8} {'Memory %':<8}")
    print("-" * 50)
    for proc in get_top_processes():
        cpu_str = colorize(proc['cpu_percent'], [70, 90])
        mem_str = colorize(proc['memory_percent'], [70, 90])
        print(f"{proc['pid']:<8} {proc['name'][:20]:<20} {cpu_str:<8} {mem_str:<8}")
    print("-" * 50)

    disk = psutil.disk_usage('/')
    print(f"Disk Usage (/)")
    print(f"Used/Total: {get_size(disk.used)} / {get_size(disk.total)}")
    print(f"Usage: {colorize(disk.percent, [70, 90])}")
    print("-" * 50)

    process_count = len(psutil.pids())
    print(f"Total Processes: {Colors.CYAN}{process_count}{Colors.RESET}")
    print("-" * 50)

    print(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"\n{Colors.BOLD}Press Ctrl+C to exit{Colors.RESET}")

def signal_handler(signum, frame, network_stats, disk_stats):
    show_cursor()
    network_stats.stop()
    disk_stats.stop()
    print(f"\n{Colors.GREEN}Exiting system monitor...{Colors.RESET}")
    sys.exit(0)

def main():
    network_stats = NetworkStats()
    disk_stats = DiskIOStats()
    signal.signal(signal.SIGINT, lambda s, f: signal_handler(s, f, network_stats, disk_stats))
    
    try:
        setup_screen()
        while True:
            print_system_info(network_stats, disk_stats)
            time.sleep(0.5)
    except KeyboardInterrupt:
        show_cursor()
        network_stats.stop()
        disk_stats.stop()
        print(f"\n{Colors.GREEN}Exiting system monitor...{Colors.RESET}")
        sys.exit(0)
    finally:
        show_cursor()
        network_stats.stop()
        disk_stats.stop()

if __name__ == "__main__":
    main()
