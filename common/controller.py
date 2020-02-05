import configparser
from configparser import ExtendedInterpolation

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
        self.config.read('settings.conf', encoding='utf-8')

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