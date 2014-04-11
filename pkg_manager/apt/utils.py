#! /usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (C) 2011 ~ 2012 Deepin, Inc.
#               2011 ~ 2012 Wang Yong
# 
# Author:     Wang Yong <lazycat.manatee@gmail.com>
# Maintainer: Wang Yong <lazycat.manatee@gmail.com>
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
from datetime import datetime
import time
from constant import LOG_PATH, SYS_CONFIG_INFO_PATH, BACKEND_PID

from deepin_utils.config import Config
from deepin_utils.file import touch_file

def set_running_lock(running):
    if running:
        touch_file(BACKEND_PID)
        with open(BACKEND_PID, "w") as file_handler:
            file_handler.write(str(os.getpid()))
    else:
        if os.path.exists(BACKEND_PID):
            os.remove(BACKEND_PID)

def log(message):
    with open(LOG_PATH, "a") as file_handler:
        now = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
        file_handler.write("%s %s\n" % (now, message))

def set_last_update_time():
    config_info_config = get_config_info_config()
    config_info_config.set("update", "last_update_time", time.time())
    config_info_config.write()

def get_config_info_config():
    config_info_config = Config(SYS_CONFIG_INFO_PATH)

    if os.path.exists(SYS_CONFIG_INFO_PATH):
        config_info_config.load()
    else:
        touch_file(SYS_CONFIG_INFO_PATH)
        config_info_config.load()

    return config_info_config
