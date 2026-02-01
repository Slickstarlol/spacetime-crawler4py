# Traceback (most recent call last):
# File "/opt/conda/lib/python3.13/dbm/sqlite3.py", line 79, in _execute
# return closing(self._cx.execute(*args, **kwargs))
# sqlite3.ProgrammingError: SQLite objects created in a thread can only
# be used in that same thread. The object was created in thread id
# 140018114819904 and this is thread id 140014634784448.

# To tackle the following problem above, added a Python key-value DB
# Removes the need for SQLITE3, which seems to be dependent on the thread
# that created them. 

import os
import shelve
import dbm.dumb  # For locking worker threads

from threading import Thread, RLock
from queue import Queue, Empty

from utils import get_logger, get_urlhash, normalize
from scraper import is_valid


class Frontier(object):
    def __init__(self, config, restart):
        self.logger = get_logger("FRONTIER")
        self.config = config
        self.to_be_downloaded = list()

        # Use an explicit lock around shelf operations
        self.save_lock = RLock()

        if not os.path.exists(self.config.save_file) and not restart:
            self.logger.info(
                f"Did not find save file {self.config.save_file}, "
                f"starting from seed.")
        elif os.path.exists(self.config.save_file) and restart:
            self.logger.info(
                f"Found save file {self.config.save_file}, deleting it.")
            os.remove(self.config.save_file)

        # Forcing the backend lock.
        db = dbm.dumb.open(self.config.save_file)
        self.save = shelve.Shelf(db, writeback=False)

        if restart:
            for url in self.config.seed_urls:
                self.add_url(url)
        else:
            self._parse_save_file()
            if not self.save:
                for url in self.config.seed_urls:
                    self.add_url(url)

    def _parse_save_file(self):
        ''' This function can be overridden for alternate saving techniques. '''
        with self.save_lock:  # Adding Lock
            total_count = len(self.save)
            tbd_count = 0
            for url, completed in self.save.values():
                if not completed and is_valid(url):
                    self.to_be_downloaded.append(url)
                    tbd_count += 1

        self.logger.info(
            f"Found {tbd_count} urls to be downloaded from {total_count} "
            f"total urls discovered.")

    def get_tbd_url(self):
        try:
            return self.to_be_downloaded.pop()
        except IndexError:
            return None

    def add_url(self, url):
        url = normalize(url)
        urlhash = get_urlhash(url)

        with self.save_lock:  # Adding Lock
            if urlhash not in self.save:
                self.save[urlhash] = (url, False)
                self.save.sync()

        # Keeping list update outside lock
        self.to_be_downloaded.append(url)

    def mark_url_complete(self, url):
        urlhash = get_urlhash(url)

        with self.save_lock:  # Adding Lock
            if urlhash not in self.save:
                self.logger.error(
                    f"Completed url {url}, but have not seen it before.")

            self.save[urlhash] = (url, True)
            self.save.sync()
