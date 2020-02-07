import configparser
from configparser import ExtendedInterpolation
import hashlib

from messengers.factory import create_messenger
from common.emojis import emoji_pc

# singleton
class GlobalController:
    __instance = None
    
    @staticmethod
    def initialize():
        if GlobalController.__instance == None:
            GlobalController.__instance = GlobalController()

    @staticmethod
    def instance():
        if GlobalController.__instance == None:
            print('Please call GlobalController.initialize() static method')
            return
        return GlobalController.__instance

    def __init__(self):
        self.messengers = {}
        self.config = configparser.ConfigParser(interpolation = ExtendedInterpolation())
        self.config_file = 'settings.conf'
        self.config.read(self.config_file, encoding='utf-8')
        self.config_hash = self.get_condig_hash()
    
    def get_condig_hash(self):
        return hashlib.md5(open(self.config_file, 'rb').read()).hexdigest()

    def update_config(self):
        new_hash = self.get_condig_hash()
        if self.config_hash == new_hash:
            return False
        else:
            self.config_hash = new_hash
            self.config.read(self.config_file, encoding='utf-8')
            return True

    def broadcast(self, msg, buttons=None, file_path=None):
        msg = emoji_pc + ' ' + self.config['CodaParams']['node_name'] + ':' + '\n' + msg
        for messenger in self.messengers.values():
            messenger.send_message(msg, buttons)
            if file_path is not None:
                messenger.send_file(file_path)

    def subscribe_to_messenger(self, name, coda_listener):
        success, self.messengers[name] = create_messenger(name, self.config)
        if not success:
            self.messengers = {}
            return
        self.messengers[name].run()
        self.messengers[name].set_coda_listener(coda_listener)
