import configparser


class DictConfigProxy(configparser.ConfigParser):
    """欺骗 Legacy 代码的 ConfigParser 代理"""

    def __init__(self, config_dict):
        super().__init__()
        self._data = config_dict

    def sections(self):
        return list(self._data.keys())

    def has_section(self, section):
        return section in self._data

    def has_option(self, section, option):
        if section not in self._data: return False
        return any(k.lower() == option.lower() for k in self._data[section].keys())

    def _get_val(self, section, option):
        if section not in self._data: raise configparser.NoSectionError(section)
        sec_data = {k.lower(): v for k, v in self._data[section].items()}
        key = option.lower()
        if key not in sec_data: raise configparser.NoOptionError(option, section)
        return sec_data[key]

    def get(self, section, option, *, raw=False, vars=None, fallback=object()):
        try:
            return str(self._get_val(section, option))
        except:
            if fallback is not object(): return fallback
            raise

    def getint(self, section, option, *, raw=False, vars=None, fallback=object()):
        try:
            return int(self._get_val(section, option))
        except:
            if fallback is not object(): return fallback
            raise

    def getfloat(self, section, option, *, raw=False, vars=None, fallback=object()):
        try:
            return float(self._get_val(section, option))
        except:
            if fallback is not object(): return fallback
            raise

    def getboolean(self, section, option, *, raw=False, vars=None, fallback=object()):
        try:
            val = self._get_val(section, option)
            if isinstance(val, bool): return val
            return str(val).lower() in ['true', '1', 'yes', 'on']
        except:
            if fallback is not object(): return fallback
            raise