import logging
import datetime

from common.controller import GlobalController

LOG_LEVEL = logging.INFO # logging.WARNING

def check_config():
	logging.basicConfig(format='%(levelname)s:%(message)s', level=LOG_LEVEL)

def info(tag, msg):
	check_config()
	logging.info('|{}|-> {}|-> : {}'.format(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'), tag, msg))

def broadcast(tag, msg, buttons=None, file_path=None):
	GlobalController.instance().broadcast(msg, buttons, file_path)

def log(tag, msg):
	check_config()
	logging.info('|--- {0} ---> : {1}'.format(tag, msg))

def warning(tag, msg):
	check_config()
	logging.warning('|---|{0} ---> : {1}'.format(tag, msg))