# Copyright (C) 2014 Red Hat, Inc., Sandro Bonazzola <sbonazzo@redhat.com>
# Copyright (C) 2013 Chris J Arges <chris.j.arges@canonical.com>
# Copyright (C) 2012-2013 Red Hat, Inc., Bryn M. Reeves <bmr@redhat.com>
# Copyright (C) 2011 Red Hat, Inc., Jesse Jaggars <jjaggars@redhat.com>

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.

import fnmatch
import os
import sos.plugintools
import tempfile


def find(file_pattern, top_dir, max_depth=None, path_pattern=None):
    """generate function to find files recursively. Usage:

    for filename in find("*.properties", /var/log/foobar):
        print filename
    """
    if max_depth:
        base_depth = os.path.dirname(top_dir).count(os.path.sep)
        max_depth += base_depth

    for path, dirlist, filelist in os.walk(top_dir):
        if max_depth and path.count(os.path.sep) >= max_depth:
            del dirlist[:]

        if path_pattern and not fnmatch.fnmatch(path, path_pattern):
            continue

        for name in fnmatch.filter(filelist, file_pattern):
            yield os.path.join(path, name)


class postgresql(sos.plugintools.PluginBase):
    """PostgreSQL related information"""

    password_warn_text = " (password visible in process listings)"

    optionList = [
        ('pghome', 'PostgreSQL server home directory.', '', '/var/lib/pgsql'),
        ('username', 'username for pg_dump', '', 'postgres'),
        ('password', 'password for pg_dump' + password_warn_text, '', False),
        ('dbname', 'database name to dump for pg_dump', '', ''),
        ('dbhost', 'database hostname/IP (do not use unix socket)', '', ''),
        ('dbport', 'database server port number', '', '5432')
    ]

    def __init__(self, pluginname, commons):
        sos.plugintools.PluginBase.__init__(self, pluginname, commons)
        self.tmp_dir = None

    def pg_dump(self):
        dest_file = os.path.join(self.tmp_dir, "sos_pgdump.tar")
        # We're only modifying this for ourself and our children so there
        # is no need to save and restore environment variables if the user
        # decided to pass the password on the command line.
        if self.getOption("password") is not False:
            os.environ["PGPASSWORD"] = str(self.getOption("password"))

        if self.getOption("dbhost"):
            cmd = "pg_dump -U %s -h %s -p %s -w -f %s -F t %s" % (
                self.getOption("username"),
                self.getOption("dbhost"),
                self.getOption("dbport"),
                dest_file,
                self.getOption("dbname")
            )
        else:
            cmd = "pg_dump -C -U %s -w -f %s -F t %s " % (
                self.getOption("username"),
                dest_file,
                self.getOption("dbname")
            )

        (status, output, rtime) = self.callExtProg(cmd)
        if (status == 0):
            self.addCopySpec(dest_file)
        else:
            self.soslog.error(
                "Unable to execute pg_dump. Error(%s)" % (output)
            )
            self.addAlert(
                "ERROR: Unable to execute pg_dump. Error(%s)" % (output)
            )

    def setup(self):
        if self.getOption("dbname"):
            if self.getOption("password") or "PGPASSWORD" in os.environ:
                self.tmp_dir = tempfile.mkdtemp()
                self.pg_dump()
            else:
                self.soslog.warning(
                    "password must be supplied to dump a database."
                )
                self.addAlert(
                    "WARN: password must be supplied to dump a database."
                )
        else:
            self.soslog.warning(
                "dbname must be supplied to dump a database."
            )
            self.addAlert(
                "WARN: dbname must be supplied to dump a database."
            )

        # Copy PostgreSQL log files.
        for filename in find("*.log", self.getOption("pghome")):
            self.addCopySpec(filename)
        # Copy PostgreSQL config files.
        for filename in find("*.conf", self.getOption("pghome")):
            self.addCopySpec(filename)

        self.addCopySpec(
            os.path.join(
                self.getOption("pghome"),
                "data",
                "PG_VERSION"
            )
        )
        self.addCopySpec(
            os.path.join(
                self.getOption("pghome"),
                "data",
                "postmaster.opts"
            )
        )

    def postproc(self):
        import shutil
        if self.tmp_dir:
            try:
                shutil.rmtree(self.tmp_dir)
            except shutil.Error:
                self.soslog.exception(
                    "Unable to remove %s." % (self.tmp_dir)
                )
                self.addAlert("ERROR: Unable to remove %s." % (self.tmp_dir))


# vim: et ts=4 sw=4
