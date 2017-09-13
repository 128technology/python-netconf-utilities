#  Copyright 2008-2015 Nokia Networks
#  Copyright 2016-     Robot Framework Foundation
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

"""Various generic utility functions and classes.

Utilities are mainly for internal usage, but external libraries and tools
may find some of them useful. Utilities are generally stable, but absolute
backwards compatibility between major versions is not guaranteed.

All utilities are exposed via the :mod:`ote_utils.utils` package, and should be
used either like::

    from ote_utils import utils

    secs = utils.timestr_to_secs("9000")

or::

    from ote_utils.utils import timestr_to_secs

    secs = utils.timestr_to_secs("9000")
"""

from .normalizing import lower, normalize, NormalizedDict
from .platform import (IRONPYTHON, JYTHON, PY2, PY3, PYPY, PYTHON, UNIXY,
                       WINDOWS, RERAISED_EXCEPTIONS)
from .robottime import (elapsed_time_to_string, format_time, get_elapsed_time,
                        get_time, get_timestamp, secs_to_timestamp,
                        secs_to_timestr, timestamp_to_secs, timestr_to_secs,
                        parse_time)
from .robottypes import (is_bytes, is_dict_like, is_falsy, is_integer,
                         is_list_like, is_number, is_string, is_truthy,
                         is_unicode, type_name)
from .unic import prepr, unic
