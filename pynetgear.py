"""
Module to communicate with Netgear routers using the SOAP v2 API.
"""
from __future__ import print_function

import re
from collections import namedtuple
import logging

import requests

_LOGGER = logging.getLogger(__name__)

Device = namedtuple(
    "Device", ["signal", "ip", "name", "mac", "type", "link_rate"])


class Netgear(object):
    """ Represents a Netgear Router. """

    def __init__(self, host, username, password):
        self.soap_url = "http://{}:5000/soap/server_sa/".format(host)
        self.username = username
        self.password = password
        self.logged_in = False

    def login(self):
        """
        Login to the router. Will be called automatically by other actions.
        """
        _LOGGER.info("Login")

        message = SOAP_LOGIN.format(session_id=SESSION_ID,
                                    username=self.username,
                                    password=self.password)

        success, _ = self._make_request(
            ACTION_LOGIN, message, False)

        self.logged_in = success

        return self.logged_in

    def get_attached_devices(self):
        """
        Returns a list of devices.
        Returns None if error occurred.
        """
        _LOGGER.info("Get attached devices")

        message = SOAP_ATTACHED_DEVICES.format(session_id=SESSION_ID)

        success, response = self._make_request(
            ACTION_GET_ATTACHED_DEVICES, message)

        if not success:
            return None

        data = re.search(r"<NewAttachDevice>(.*)</NewAttachDevice>",
                         response).group(1).split(";")

        devices = []

        device_start = [index for index, value in enumerate(data)
                        if '@' in value]

        for index, start in enumerate(device_start):
            try:
                info = data[start:device_start[index+1]]
            except IndexError:
                # The last device, ignore the last element
                info = data[start:-1]

            signal = convert(info[0].split("@")[0], int)
            ip, name, mac, link_type = info[1:5]
            link_rate = convert(info[-1], int)

            devices.append(Device(signal, ip, name, mac, link_type, link_rate))

        return devices

    def _make_request(self, action, message, try_login_after_failure=True):
        """ Make an API request to the router. """

        # If we are not logged in, the request will fail for sure.
        if not self.logged_in and try_login_after_failure:
            if not self.login():
                return False, ""

        headers = _get_soap_header(action)

        try:
            req = requests.post(
                self.soap_url, headers=headers, data=message, timeout=10)

            success = _is_valid_response(req)

            if not success and try_login_after_failure:
                self.login()

                req = requests.post(
                    self.soap_url, headers=headers, data=message, timeout=10)

                success = _is_valid_response(req)

            return success, req.text

        except requests.exceptions.RequestException:
            _LOGGER.exception("Error talking to API")

            # Maybe one day we will distinguish between
            # different errors..
            return False, ""


def _get_soap_header(action):
    return {"SOAPAction": action}


def _is_valid_response(resp):
    return (resp.status_code == 200 and
            "<ResponseCode>000</ResponseCode>" in resp.text)


def convert(value, to_type, default=None):
    """ Converts value to to_type, returns default if fails. """
    try:
        return default if value is None else to_type(value)
    except ValueError:
        # If value could not be converted
        return default


ACTION_LOGIN = "urn:NETGEAR-ROUTER:service:ParentalControl:1#Authenticate"
ACTION_GET_ATTACHED_DEVICES = "urn:NETGEAR-ROUTER:service:DeviceInfo:1#GetAttachDevice"

# Until we know how to generate it, give the one we captured
SESSION_ID = "A7D88AE69687E58D9A00"

SOAP_LOGIN = """<?xml version="1.0" encoding="utf-8" ?>
<SOAP-ENV:Envelope xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/">
<SOAP-ENV:Header>
<SessionID xsi:type="xsd:string" xmlns:xsi="http://www.w3.org/1999/XMLSchema-instance">{session_id}</SessionID>
</SOAP-ENV:Header>
<SOAP-ENV:Body>
<Authenticate>
  <NewUsername>{username}</NewUsername>
  <NewPassword>{password}</NewPassword>
</Authenticate>
</SOAP-ENV:Body>
</SOAP-ENV:Envelope>"""

SOAP_ATTACHED_DEVICES = """<?xml version="1.0" encoding="utf-8" standalone="no"?>
<SOAP-ENV:Envelope xmlns:SOAPSDK1="http://www.w3.org/2001/XMLSchema" xmlns:SOAPSDK2="http://www.w3.org/2001/XMLSchema-instance" xmlns:SOAPSDK3="http://schemas.xmlsoap.org/soap/encoding/" xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/">
<SOAP-ENV:Header>
<SessionID>{session_id}</SessionID>
</SOAP-ENV:Header>
<SOAP-ENV:Body>
<M1:GetAttachDevice xmlns:M1="urn:NETGEAR-ROUTER:service:DeviceInfo:1">
</M1:GetAttachDevice>
</SOAP-ENV:Body>
</SOAP-ENV:Envelope>
"""


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 4:
        print("To test: python pynetgear.py <host> <user> <pass>")
        sys.exit()

    logging.basicConfig(level=logging.INFO)

    host, username, password = sys.argv[1:]

    netgear = Netgear(host, username, password)

    devices = netgear.get_attached_devices()

    if devices is None:
        print("Error communicating with the Netgear router")

    else:
        for i in devices:
            print(i)
