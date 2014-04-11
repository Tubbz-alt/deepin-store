#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# Copyright (C) 2011 ~ 2012 Deepin, Inc.
#               2011 ~ 2012 Wang Yong
#               2012 ~ 2013 Kaisheng Ye
# 
# Author:     Wang Yong <lazycat.manatee@gmail.com>
# Maintainer: Wang Yong <lazycat.manatee@gmail.com>
#             Kaisheng Ye <kaisheng.ye@gmail.com>
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

from deepin_utils.file import get_parent_dir
import os
import sys
import sqlite3
from collections import OrderedDict
import xappy
from data import DATA_ID
from constant import LANGUAGE

UPDATE_DATA_DIR = os.path.join(get_parent_dir(__file__, 2), "data", "update", DATA_ID)
CACHE_SOFT_DB_PATH = os.path.join(get_parent_dir(__file__, 2), "data", "cache_soft.db")

DATA_SUPPORT_LANGUAGE = ['en_US', 'zh_CN', 'zh_TW', 'zh_HK']

def db_path_exists(path):
    if not os.path.exists(path):
        print "Database not exist:", path
        sys.exit(1)

class DataManager(object):
    '''
    class docs
    '''
	
    def __init__(self, bus_interface, debug_flag=False):
        '''
        init docs
        '''
        self.bus_interface = bus_interface
        self.debug_flag = debug_flag

        self.language = LANGUAGE if LANGUAGE in DATA_SUPPORT_LANGUAGE else 'en_US'
        
        software_db_path = os.path.join(UPDATE_DATA_DIR, "software", self.language, "software.db")
        db_path_exists(software_db_path)
        self.software_db_connect = sqlite3.connect(software_db_path)
        self.software_db_cursor = self.software_db_connect.cursor()

        self.init_cache_soft_db()

        desktop_db_path = os.path.join(UPDATE_DATA_DIR, "desktop", self.language, "desktop.db")
        db_path_exists(desktop_db_path)
        self.desktop_db_connect = sqlite3.connect(desktop_db_path)
        self.desktop_db_cursor = self.desktop_db_connect.cursor()
        
        category_db_path = os.path.join(UPDATE_DATA_DIR, "category", "category.db")
        db_path_exists(category_db_path)
        self.category_db_connect = sqlite3.connect(category_db_path)
        self.category_db_cursor = self.category_db_connect.cursor()
        
        self.category_dict = {}
        self.category_name_dict = {}
        
        self.build_category_dict()

    def init_cache_soft_db(self):
        if self.is_cache_soft_db_exists() and not hasattr(self, 'cache_soft_db_cursor'):
            self.cache_soft_db_connect = sqlite3.connect(CACHE_SOFT_DB_PATH)
            self.cache_soft_db_cursor = self.cache_soft_db_connect.cursor()

    def is_cache_soft_db_exists(self):
        return os.path.exists(CACHE_SOFT_DB_PATH)

    def get_info_from_cache_soft_db(self, argv):
        if self.is_cache_soft_db_exists():
            if not hasattr(self, 'cache_soft_db_cursor'):
                self.cache_soft_db_connect = sqlite3.connect(CACHE_SOFT_DB_PATH)
                self.cache_soft_db_cursor = self.cache_soft_db_connect.cursor()
            self.cache_soft_db_cursor.execute(*argv)
            return self.cache_soft_db_cursor.fetchall()
        else:
            return []

    def get_pkgs_match_input(self, input_string):
        # Select package name match input string.

        input_string = input_string.lower()
        pkg_names = []
        argv = [
            "SELECT pkg_name FROM software WHERE pkg_name LIKE ?",
            ("%" + unicode(input_string) + "%",)
            ]

        cache_info = self.get_info_from_cache_soft_db(argv)
        if cache_info:
            for (pkg_name, ) in cache_info:
                pkg_names.append(pkg_name)
        else:
            self.software_db_cursor.execute(*argv)
            for (pkg_name, ) in self.software_db_cursor.fetchall():
                pkg_names.append(pkg_name)
            
        # Sort package name.
        pkg_names = sorted(
            pkg_names,
            cmp=lambda pkg_name_a, pkg_name_b: self.sort_match_pkgs(pkg_name_a, pkg_name_b, input_string))    
            
        return pkg_names
    
    def sort_match_pkgs(self, pkg_name_a, pkg_name_b, input_string):
        start_with_a = pkg_name_a.startswith(input_string)
        start_with_b = pkg_name_b.startswith(input_string)
        
        if start_with_a and start_with_b:
            return cmp(pkg_name_a, pkg_name_b)
        elif start_with_a:
            return -1
        else:
            return 1

    def get_pkgs_install_status(self, pkg_names, reply_handler, error_handler):
        return self.bus_interface.request_pkgs_install_status(
            pkg_names,
            reply_handler=reply_handler,
            error_handler=error_handler)

    def get_pkg_download_size(self, pkg_name, callback):
        self.bus_interface.get_download_size(
                pkg_name,
                reply_handler=lambda r: callback(r, True),
                error_handler=lambda e: callback(e, False)
                )
        
    def get_search_pkgs_info(self, pkg_names):
        pkg_infos = []
        for (index, pkg_name) in enumerate(pkg_names):
            self.desktop_db_cursor.execute(
                "SELECT desktop_path, icon_name, display_name FROM desktop WHERE pkg_name=?", [pkg_name])    
            desktop_infos = self.desktop_db_cursor.fetchall()
            pkg_infos.append([pkg_name, desktop_infos])
        
        return pkg_infos
    
    def get_pkg_desktop_info(self, pkg_name):
        self.desktop_db_cursor.execute(
            "SELECT desktop_path, icon_name, display_name FROM desktop WHERE pkg_name=?", [pkg_name])    
        return self.desktop_db_cursor.fetchall()
    
    def get_pkg_installed(self, pkg_name, callback):
        self.bus_interface.get_pkg_installed(pkg_name,
                reply_handler=lambda r: callback(r, True),
                error_handler=lambda e: callback(e, False)
                )
        
    def get_pkg_detail_info(self, pkg_name):
        result = {
                'category': None,
                'recommend_pkgs': [],
                'long_desc': 'Unknown',
                'version': 'Unknown',
                'homepage': '',
                'alias_name': pkg_name,
                }

        # get category, recommend_pkgs
        self.desktop_db_cursor.execute(
            "SELECT first_category_name, second_category_name FROM desktop WHERE pkg_name=?", [pkg_name])
        category_names = self.desktop_db_cursor.fetchone()
        if category_names and category_names[0] and category_names[1]:
            result['category'] = category_names
            self.category_db_cursor.execute(
                "SELECT recommend_pkgs FROM category_name WHERE first_category_name=? and second_category_name=?",
                [category_names[0], category_names[1]])
            names = eval(self.category_db_cursor.fetchone()[0])
            for name in names:
                if name != pkg_name:
                    self.software_db_cursor.execute(
                        "SELECT alias_name FROM software WHERE pkg_name=?", [name])
                    alias_name = self.software_db_cursor.fetchone()[0]
                    result['recommend_pkgs'].append((name, alias_name, 5.0))

        # get long_desc, version, homepage, alias_name
        self.software_db_cursor.execute(
            "SELECT long_desc, alias_name FROM software WHERE pkg_name=?", [pkg_name])
        info = self.software_db_cursor.fetchone()

        if info:
            result["long_desc"] = info[0]
            result["alias_name"] = info[1]

        cache_info = self.get_info_from_cache_soft_db([
            "SELECT long_desc, version, homepage FROM software WHERE pkg_name=?",
            [pkg_name]])
        if cache_info:
            if result['long_desc'] == 'Unknown': result['long_desc'] = cache_info[0][0]
            result['version'] = cache_info[0][1]
            result['homepage'] = cache_info[0][2]
        return result
        
    def get_pkg_search_info(self, pkg_name):
        self.software_db_cursor.execute(
            "SELECT alias_name, short_desc, long_desc FROM software WHERE pkg_name=?", [pkg_name])
        result = self.software_db_cursor.fetchone()
        
        if result == None:
            cache_info = self.get_info_from_cache_soft_db([
                "SELECT short_desc, long_desc FROM software WHERE pkg_name=?",
                [pkg_name]])
            if cache_info:
                (short_desc, long_desc) = cache_info[0]
                return (pkg_name, short_desc, long_desc, 5.0)
            else:
                return (pkg_name, "FIXME", "FIXME", 5.0)
        else:
            (alias_name, short_desc, long_desc) = result
            return (alias_name, short_desc, long_desc, 5.0)
    
    def get_item_pkg_info(self, pkg_name):
        self.software_db_cursor.execute(
            "SELECT short_desc, alias_name FROM software WHERE pkg_name=?", [pkg_name])
        info = self.software_db_cursor.fetchone()
        if info == None:
            return (None, 5.0, pkg_name)
        else:
            (short_desc, alias_name) = info
            return (short_desc, 5.0, alias_name)
    
    def get_item_pkgs_info(self, pkg_names):
        infos = []
        for (index, pkg_name) in enumerate(pkg_names):
            (short_desc, star, alias_name) = self.get_item_pkg_info(pkg_name)
            infos.append([pkg_name, short_desc, star, alias_name])
            
        return infos    
    
    def is_pkg_have_desktop_file(self, pkg_name):
        if pkg_name.endswith(":i386"):
            pkg_name = pkg_name[:-5]
        self.desktop_db_cursor.execute(
            "SELECT desktop_path FROM desktop WHERE pkg_name=?", [pkg_name])
        return self.desktop_db_cursor.fetchone()

    def is_pkg_display_in_uninstall_page(self, pkg_name):
        if pkg_name.endswith(":i386"):
            pkg_name = pkg_name[:-5]
        self.desktop_db_cursor.execute(
            "SELECT display_flag FROM desktop WHERE pkg_name=?", [pkg_name])
        return self.desktop_db_cursor.fetchone()
    
    def get_album_info(self):
        self.album_db_cursor.execute(
            "SELECT album_id, album_name, album_summary FROM album ORDER BY album_id")
        return self.album_db_cursor.fetchall()
    
    def get_album_detail_info(self, album_id):
        self.album_db_cursor.execute(
            "SELECT pkg_name, pkg_title, pkg_summary FROM album_pkg WHERE album_id=? ORDER BY pkg_sort_id", 
            [album_id])
        infos = self.album_db_cursor.fetchall() 
        pkg_names = map(lambda info: info[0], infos)
        
        install_status = self.bus_interface.request_pkgs_install_status(pkg_names)
        
        detail_infos = []
        for (index, (pkg_name, pkg_title, pkg_summary)) in enumerate(infos):
            self.software_db_cursor.execute(
                "SELECT alias_name FROM software WHERE pkg_name=?", [pkg_name])
            (alias_name,) = self.software_db_cursor.fetchone()
            
            self.desktop_db_cursor.execute(
                "SELECT desktop_path, icon_name, display_name FROM desktop WHERE pkg_name=?", [pkg_name])    
            desktop_infos = self.desktop_db_cursor.fetchall()
            
            detail_infos.append((pkg_name, pkg_title, pkg_summary, alias_name, desktop_infos, install_status[index]))
        
        return detail_infos
    
    def get_download_rank_info(self, pkg_names):
        infos = []

        for pkg_name in pkg_names:

            self.software_db_cursor.execute(
                "SELECT alias_name FROM software WHERE pkg_name=?", [pkg_name])
            r = self.software_db_cursor.fetchone()
            if r != [] and r != None:
                alias_name = r[0]
            
                self.desktop_db_cursor.execute(
                    "SELECT desktop_path, icon_name, display_name FROM desktop WHERE pkg_name=?", [pkg_name])    
                desktop_infos = self.desktop_db_cursor.fetchall()
                
                infos.append([pkg_name, alias_name, 5.0, desktop_infos])
            
        return infos

    def get_recommend_info(self):
        pkgs = []
        with open(self.recommend_db_path) as fp:
            for line in fp:
                pkgs.append(line.strip())
        return pkgs

    def get_slide_info(self):
        pkgs = []
        with open(self.slide_db_path) as fp:
            for line in fp:
                pkgs.append(line.strip())
        return pkgs
    
    def build_category_dict(self):
        # Build OrderedDict of first category.
        self.category_db_cursor.execute(
            "SELECT DISTINCT first_category_name FROM category_name ORDER BY first_category_index")
        self.category_dict = OrderedDict(map(lambda names: (names[0], []), self.category_db_cursor.fetchall()))
        
        # Build list of second category. 
        self.category_db_cursor.execute(
            "SELECT DISTINCT first_category_name, second_category_name FROM category_name ORDER BY second_category_index")
        for (first_category, second_category) in self.category_db_cursor.fetchall():
            self.category_dict[first_category] = self.category_dict[first_category] + [(second_category, OrderedDict())]
            
        # Bulid OrderedDict of second category.
        for (first_category, second_category_list) in self.category_dict.items():
            self.category_dict[first_category] = OrderedDict(second_category_list)

        # Fill data into category dict.
        self.category_name_dict = OrderedDict()
        self.category_db_cursor.execute(
            "SELECT first_category_index, second_category_index, first_category_name, second_category_name FROM category_name")
        for (first_category_index, second_category_index, first_category, second_category) in self.category_db_cursor.fetchall():
            self.category_name_dict[(first_category_index, second_category_index)] = (first_category, second_category)
            
    def get_category_pkg_info(self):
        # Category dict format:
        # 
        # category_dict = {
        #     first_category : {
        #         second_category : {
        #             pkg_name : [(desktop_path, icon_name)]
        #             }
        #         }
        #     }
    
        self.desktop_db_cursor.execute(
            "SELECT desktop_path, pkg_name, icon_name, display_name, first_category_name, second_category_name FROM desktop ORDER BY display_name")
        for (desktop_path, pkg_name, icon_name, display_name, first_category_name, second_category_name) in self.desktop_db_cursor.fetchall():
            if first_category_name != "" and second_category_name != "":
                
                second_category_dict = self.category_dict[first_category_name][second_category_name]    
                if not second_category_dict.has_key(pkg_name):
                    second_category_dict[pkg_name] = []
                    
                pkg_list = second_category_dict[pkg_name] 
                second_category_dict[pkg_name] = pkg_list + [(desktop_path, icon_name, display_name)]
            
        return self.category_dict    
    
    def get_second_category_pkg_info(self, first_category):
        return self.category_dict[first_category]
                
    def search_query(self, keywords):
        '''
        init docs
        '''
        # Init search connect.
        search_db_path = os.path.join(UPDATE_DATA_DIR, "search", "zh_CN", "search_db")
        sconn = xappy.SearchConnection(search_db_path)
        
        # Do search.
        search = ' '.join(keywords).lower()
        q = sconn.query_parse(search, default_op=sconn.OP_AND)
        results = sconn.search(q, 0, sconn.get_doccount(), sortby="have_desktop_file")
        
        all_results = map(lambda result: result.data["pkg_name"][0], results)
        for keyword in keywords:
            match_names = self.get_pkgs_match_input(keyword)
            for name in match_names:
                if name not in all_results:
                    all_results.append(name)
        return all_results

    def change_source_list(self, repo_urls, reply_handler, error_handler):
        self.bus_interface.change_source_list(repo_urls,
                reply_handler=reply_handler, 
                error_handler=error_handler)
        
if __name__ == "__main__":
    import dbus
    from constant import DSC_SERVICE_NAME, DSC_SERVICE_PATH
    system_bus = dbus.SystemBus()
    bus_object = system_bus.get_object(DSC_SERVICE_NAME, DSC_SERVICE_PATH)
    bus_interface = dbus.Interface(bus_object, DSC_SERVICE_NAME)

    data_manager = DataManager(bus_interface)
    #print data_manager.get_all_download_rank_info()
    #print data_manager.get_month_download_rank_info()
    #print data_manager.get_week_download_rank_info()
    for info in  data_manager.get_album_detail_info(0):
        print info

