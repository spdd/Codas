from time import sleep
import subprocess
import json
import datetime
from argparse import ArgumentParser

from common.scheduler import RepeatedTimer
from common import logger
from common.controller import GlobalController
from common.emojis import *

class Codas(object):
    def __init__(self, config):
        self.observe = True
        self.insecure_rest = False
        self.timer = None
        self.timer_inverval = int(config['Codas']['timer_inverval'])
        self.only_block_production = True if int(config['CodaParams']['only_block_production']) == 1 else False
        self.snark_worker_stopped = True
        self.staking_stopped = True
        self.config = config
        self.daemon_screen_pid = None
        self.daemon_pid = 0
        self.pids = {}
        self.block_height = 0
        self.iblock = 0
        self.icrash = 0
        self.coda_uptime = None
        self.restart_after = 5 # iterations for restart coda after: timer_inverval * restart_after
        self.not_synced_statuses = 'Crash Offline Listening Bootstrap Catchup'
        self.not_synced_count = 0
        self.crash_report = None
        self.sending_report = False
        self.not_running_count = 0

    def start(self):
        self.start_timer()
        self.check_coda()

    def run(self, command):
        return subprocess.Popen([command], stdout=subprocess.PIPE, shell = True).communicate()[0].decode("utf-8").replace("\n", "")

    def run_detach(self, command):
        self.daemon_screen_pid = subprocess.Popen([command], stdout=subprocess.PIPE, shell = True, close_fds=True).pid
        self.daemon_screen_pid += 2
        self.add_pid('daemon_screen', self.daemon_screen_pid)
        logger.info("Codas", "{} daemon screen pid: {}".format(emoji_key, self.daemon_screen_pid))

    def add_pid(self, name, pid):
        self.pids[name] = pid

    def find_crash_report(self):
        return self.run(self.config['CodaCmd']['find_crash_report_path']) 

    def get_coda_status(self):
        result = self.run(self.config['CodaCmd']['get_status'])
        not_json = False
        try:
            result = json.loads(result)
        except Exception:
            not_json = True
            logger.info("Codas", "get_status is not json")

        sync_status = 'Crash' if not_json else result['sync_status']
        #logger.info("Codas", "Coda status: {}".format(sync_status))
        if sync_status != 'Crash':
            return True, result
        else:
            return False, json.loads('{"sync_status": "Crash", "blockchain_length": "-", "uptime_secs": "0", "next_proposal":"at in 11000h"}')

    def start_snark_worker(self):
        if self.observe: return
        result = self.run(self.config['CodaCmd']['run_snark_worker'].format(self.config['CodaParams']['public_key']))
        self.snark_worker_stopped = False
        logger.info("Codas", "{} Snark worker started!".format(emoji_face_rinning))
        return result

    def start_snark_workers(self):
        if self.observe: return
        pass

    def stop_snark_workers(self):
        if self.observe: return
        for name, pid in self.pids.items():
            if 'snark worker' in name:
                self.kill_process(name, pid)
        self.snark_worker_stopped = True
        logger.info("Codas", '{} All Snark workers stopped!'.format(emoji_cross_mark))

    def stop_snark_worker(self):
        if self.observe: return
        result = self.run(self.config['CodaCmd']['stop_snark_worker'])
        self.snark_worker_stopped = True
        msg = "{} Snark worker stopped!".format(emoji_face_confused)
        logger.info("Codas", msg)
        logger.broadcast("Codas", msg)
        return result

    def stop_coda(self):
        if self.observe: return
        self.kill_process('daemon', self.pids['daemon'])
        self.kill_process('daemon_screen', self.pids['daemon_screen'])
        self.staking_stopped = True
        msg = '{} Coda daemon stopped process: {}'.format(emoji_cross_mark, self.pids['daemon'])
        logger.info("Codas", msg)
        logger.broadcast("Codas", msg)
    
    def stop_all_coda(self):
        self.stop_coda()
        self.run(self.config['CodaCmd']['kill_coda'])
        self.not_running_count = 0

    def stop_coda_and_snark_workers(self):
        if self.observe: return
        self.stop_coda()
        self.stop_snark_workers()
        self.icrash = 0
        self.not_synced_count = 0
        self.iblock = 0
        self.pids = {}

    def kill_process(self, name, pid):
        stop_process_cmd = 'kill -9 {}'.format(pid)
        self.run(stop_process_cmd)
        msg = "{} Killed {} process pid: {}".format(emoji_cross_mark, name, pid)
        logger.info("Codas", msg)

    def start_staking(self):
        if self.observe: return
        logger.info("Codas", "{} Staking starting...".format(emoji_neutral_face))
        cmd = self.config['CodaCmd']['start_coda'].format(
            self.config['CodaParams']['wallet_password'], 
            self.config['CodaParams']['peer1'], 
            self.config['CodaParams']['peer2'],
            self.config['CodaParams']['wallet_path'],
            '-insecure-rest-server' if self.insecure_rest else '')
        self.run_detach(cmd)
        logger.info("Codas", '{} Staking started!'.format(emoji_face_grimacing))
        self.staking_stopped = False

    def get_coda_processes(self):
        process_list = subprocess.Popen([self.config['CodaCmd']['check_process']], stdout=subprocess.PIPE, shell = True).communicate()[0].decode("utf-8").split("\n")
        if len(process_list) == 1:
            if process_list[0] == '':
                if self.not_running_count == 3:
                    self.stop_all_coda()
                else:
                    self.not_running_count += 1
                return [], '{} Coda not running, 0 processes'.format(emoji_face_confused)
        else: 
            self.not_running_count = 0
            process_list = process_list[:-1]
        for i, pid in enumerate(process_list):
            if pid.isdigit():
                if int(pid) == self.daemon_pid:
                    continue
                if int(pid) in self.pids.values(): 
                    continue
                if len(self.pids.values()) == 0:
                    self.daemon_pid = int(pid)
                    self.add_pid('daemon', int(pid))
                else: 
                    self.add_pid('snark worker ' + str(i), int(pid))
        
        logger.info("Codas", "{} Pids: {}".format(emoji_key, self.pids))

        msg = '{} Coda pid: {} Snark workers: {}'.format(emoji_key, (self.daemon_pid if self.daemon_pid is not None else 0), len(self.pids.values()) - 1)
        return self.pids.values(), msg
    
    def get_balance(self):
        balance = self.run(self.config['CodaCmd']['get_balance'].format(self.config['CodaParams']['public_key']))
        msg = '{} {}'.format(emoji_money_wings, balance)
        logger.broadcast('Codas', msg)
        return balance

    def unlock_wallet(self):
        self.run(self.config['CodaCmd']['unlock_wallet'].format(self.config['CodaParams']['wallet_password'], self.config['CodaParams']['public_key']))

    def send_payment(self, recipient, amount, fee = 5):
        self.unlock_wallet()
        payment_id = self.run(self.config['CodaCmd']['send_payment'].format(
            amount,
            recipient,
            fee,
            self.config['CodaParams']['public_key'])
        )
        return payment_id

    def get_next_proposal_time(self, proposal_str):
        result = proposal_str.split('in')
        in_hours = result[len(result)-1].strip()
        if 'h' in in_hours:
            result = in_hours.replace('h', '').split('.')
            minutes = (int(result[0]) * 60) + int(result[1][0:2])
        elif 'm' in in_hours:
            result = in_hours.replace('m', '').split('.')
            minutes = int(result[0])
        else:
            minutes = 1
        return in_hours, minutes        

    def set_block_height(self, block_height):
        if int(block_height) > self.block_height:
            self.block_height = int(block_height)
            self.iblock = 0
        elif int(block_height) == self.block_height:
            time_stuck_in_min = (self.iblock * self.timer_inverval)/60
            # block stuck > 10(default) min send message to restart or ...
            if time_stuck_in_min > int(self.config['Codas']['time_block_height_stuck']):
                msg = "{} Coda gets stuck on {} block".format(emoji_face_confused, self.block_height)
                logger.info("Codas", msg)
                logger.broadcast("Codas", msg, ['Status'])

    def check_crash_report(self):
        if not self.sending_report:
            return
        report_path = self.find_crash_report()
        if 'coda_crash_report' not in report_path:
            return
        else:
            if self.crash_report == report_path:
                return
            logger.info('Codas', '{} Crash report path: {}'.format(emoji_pile_of_poo, report_path))
            self.crash_report = report_path
            tmp = report_path.split('/')[-1].split('_') 
            date1 = tmp[-2] # '2020-02-03'
            date2 = tmp[-1].split('.')[0].split('-')[0:2] # ['03', '39']
            full_date_str = '{}-{}-{}'.format(date1, date2[0], date2[1])
            date = datetime.datetime.strptime(full_date_str , '%Y-%m-%d-%I-%M')
            time_difference = datetime.datetime.now() - date
            diff_in_minutes = (time_difference.days * 24 * 60) + (time_difference.seconds / 60)
            # if < 300 minutes (default) then report is new
            if diff_in_minutes <= int(self.config['Codas']['time_how_old_report']): 
                logger.broadcast("Codas", 'You have a new crash report.', None , report_path)

    def update_config(self):
        if GlobalController.instance().update_config():
            logger.info("Codas", "{} Config updated".format(emoji_biceps))

    def check_coda(self):
        self.update_config()
        self.check_crash_report()
        self.iblock += 1
        fresh_running = False
        coda_running, status_result = self.get_coda_status()
        status = status_result['sync_status']
        if status in self.not_synced_statuses:
            # if not status gets stuck on not synced status then restart coda
            if self.not_synced_count >= int(self.config['Codas']['time_not_synced']):
                 self.stop_coda_and_snark_workers()
                 return
            self.not_synced_count += 1

        # run coda if crashed
        list_of_coda_processes, msg_processes = self.get_coda_processes()
        logger.info("Codas", msg_processes)
        msg_status = ''
        if not coda_running and (len(list_of_coda_processes) == 0):
            self.start_staking()
            fresh_running = True
            msg_status = '{} Coda started running...'.format(emoji_face_rinning) # status_result
        else:
            # if crached and not running over 5 (icrash * timer_interval) minutes and process is exist then kill all coda processes
            if not coda_running:
                if self.icrash > self.restart_after:
                    self.stop_coda_and_snark_workers()
                    return
                self.icrash += 1
            msg_status = "{} Current Status: {}".format(emoji_cross_mark if status == 'Crash' else emoji_circle_arrows , status)
            
        if fresh_running: return
        # Stop and start snark worker depend on proposal time
        str_in_hours = ''
        msg_proposal = ''
        msg_block_height = ''
        if status == 'Synced':
            self.not_synced_count = 0
            msg_status = "{} Current Status: {}".format(emoji_heck_mark, status)
            str_in_hours, proposal_minutes = self.get_next_proposal_time(status_result['next_proposal'])
            msg_proposal = '{} Next Proposal: in {} ({} minutes)'.format(emoji_calendar ,str_in_hours, proposal_minutes)
            logger.info("Codas", msg_proposal)

            if not self.only_block_production:
                if not self.snark_worker_stopped and proposal_minutes <= int(self.config['Codas']['time_stop_snarkworker_before_proposal']):
                    self.stop_snark_worker()
                if self.snark_worker_stopped and proposal_minutes > int(self.config['Codas']['time_start_snarkworker_after_proposal']):
                    self.start_snark_worker() 

            self.coda_uptime = str(datetime.timedelta(seconds=int(status_result['uptime_secs'])))
            block_height = status_result['blockchain_length']
            self.set_block_height(block_height)
            msg_block_height = '{} Block Number: {}\n{} Uptime: {}'.format(emoji_chain, block_height, emoji_clock, self.coda_uptime)

        logger.info("Codas", msg_status)

        msg_snark = ''
        if not self.snark_worker_stopped:
            msg_snark = "{} Snark Worker: Enabled".format(emoji_fire)
        else: 
            msg_snark = "{} Snark Worker: Disabled".format(emoji_snowflake)
        logger.info("Codas", msg_snark)
     
        msg =  msg_status + '\n' + msg_block_height + '\n' + msg_processes + '\n' + msg_snark + '\n' + msg_proposal
        logger.broadcast("Codas", msg, ['Balance'])

    def start_timer(self):
        self.timer = RepeatedTimer(self.timer_inverval, self.check_coda)
        logger.info("Codas", 'Start scheduler repeat every {} seconds'.format(self.timer_inverval))      

    def stop_timer(self, status):
        self.timer.stop()
        self.timer = None
        logger.info("Codas", 'Stop scheduler for {}'.format(status))

    class CodaListener(object):
        def __init__(self, codas):
            self.codas = codas

        def on_start_snark_worker(self):
            return self.codas.start_snark_worker()
        
        def on_stop_snark_worker(self):
            return self.codas.stop_snark_worker()

        def on_stop_coda_and_snark_workers(self):
            self.codas.stop_coda_and_snark_workers()

        def on_start_staking(self):
            return self.codas.start_staking()

        def on_get_coda_status(self):
            return self.codas.get_coda_status()
        
        # wallet
        def on_get_balance(self):
            return self.codas.get_balance()

        def on_send_payment(self, recipient, amount, fee = 5):
            return self.codas.send_payment(recipient, amount, fee)

if __name__ == "__main__": 
    parser = ArgumentParser(description='Codas!')
    parser = ArgumentParser()
    parser.add_argument("-o", "--disable_observe", help="Observe coda daemon, but not restart or stop", action="store_true")
    parser.add_argument("-r", "--send_report", help="Send crash reports to messengers", action="store_true")
    parser.add_argument("-t", "--insecure_rest", help="Open to everyone graphql rest server not just localhost", action="store_true")
    parser.add_argument("-m", "--messenger", type=str, default="", help="Use to send notifications to messengers")
    args = parser.parse_args()

    GlobalController.initialize()
    running = False
    if not running:
        codas = Codas(GlobalController.instance().config)
        if args.disable_observe:
            codas.observe = False
        logger.info("Codas", "{} Observation mode: {}".format(emoji_alarm_clock, codas.observe))
        if args.send_report:
            codas.sending_report = True
        if args.insecure_rest:
            codas.insecure_rest = True
        logger.info("Codas", "{} Insecure rest server: {}".format(emoji_alarm_clock, codas.insecure_rest))
        logger.info("Codas", "{} Sending crash report: {}".format(emoji_hundred, codas.sending_report))
        if args.messenger != '':
            coda_listener = Codas.CodaListener(codas)
            GlobalController.instance().subscribe_to_messenger(args.messenger, coda_listener)
            logger.info("Codas", "{} Subscribed to {} messenger".format(emoji_rocket, args.messenger))
        codas.start()
        running = True
