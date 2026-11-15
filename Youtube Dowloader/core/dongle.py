"""
4G USB dongle ("HiMI 4G UFI") as a backup line for YouTube.

YouTube's "confirm you're not a bot" check is tied to the IP. Rebooting the
dongle makes it dial the carrier again, which normally hands out a new mobile
IP, so a blocked download can retry without cookies.

Check the setup:        python core/dongle.py
Try one reboot by hand: python core/dongle.py --reset
"""
import http.client
import json
import os
import socket
import sys
import time

if __package__ in (None, ''):  # run as a script: make the tool folder importable
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import DONGLE_HOST, DONGLE_PASSWORD

_NET_ERRORS = (OSError, http.client.HTTPException, ValueError)
_BACK_ONLINE_TIMEOUT = 180  # boot + dial normally takes about a minute


def local_ip() -> str:
    """This PC's address on the dongle's network, or '' when it is not plugged in."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect((DONGLE_HOST, 80))  # UDP: only picks a route, sends nothing
            ip = s.getsockname()[0]
    except OSError:
        return ''
    return ip if ip.rsplit('.', 1)[0] == DONGLE_HOST.rsplit('.', 1)[0] else ''


def available() -> bool:
    """Plugged in and allowed to reboot it."""
    return bool(DONGLE_PASSWORD) and bool(local_ip())


def public_ip(source_ip: str = '') -> str:
    """Public IP as seen through source_ip's connection ('' = Windows' default)."""
    conn = http.client.HTTPSConnection(
        'api.ipify.org', timeout=10, source_address=(source_ip, 0) if source_ip else None)
    try:
        conn.request('GET', '/')
        return conn.getresponse().read().decode().strip()
    except _NET_ERRORS:
        return ''
    finally:
        conn.close()


def _call(cmdid: str, session: str = '', **fields) -> dict:
    body = dict(fields, cmdid=cmdid, sessionId=session)
    headers = {'Content-Type': 'application/json;charset=UTF-8'}
    if session:
        headers['Authorization'] = session
    conn = http.client.HTTPConnection(DONGLE_HOST, 80, timeout=10)
    try:
        conn.request('POST', '/himiapi/json', json.dumps(body), headers)
        return json.loads(conn.getresponse().read() or b'{}')
    finally:
        conn.close()


def is_dongle() -> bool:
    """True if DONGLE_HOST answers like the HiMI firmware (and not, say, a home router)."""
    try:
        reply = _call('getconfig')
    except _NET_ERRORS:
        return False
    return reply.get('reply') == 'ok' and 'HiMI' in str(reply.get('copyrights', ''))


def reboot() -> str:
    """Log in and reboot the dongle. Returns '' on success, otherwise why not.

    rebootcmd is the only write command sent from here, and only ever with
    'reboot': the very same command with 'freset' wipes the dongle back to
    factory settings.
    """
    if not DONGLE_PASSWORD:
        return 'chưa điền DONGLE_PASSWORD trong config.py'
    if not is_dongle():
        return f'{DONGLE_HOST} không phải dongle HiMI 4G UFI'
    try:
        login = _call('login', username='admin', password=DONGLE_PASSWORD)
    except _NET_ERRORS as e:
        return f'không đăng nhập được dongle: {e}'
    session = login.get('session')
    if login.get('reply') != 'ok' or not session:
        return 'sai mật khẩu dongle (DONGLE_PASSWORD trong config.py)'
    try:
        reply = _call('rebootcmd', session, params='reboot')
    except _NET_ERRORS:
        return ''  # it went down before answering, which is what we asked for
    if reply.get('reply') != 'ok':
        return f"dongle không nhận lệnh reboot ({reply.get('reply')})"
    return ''


def _wait_until(check, timeout):
    """Poll check() until it returns something truthy; that value, or '' on timeout."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = check()
        if value:
            return value
        time.sleep(3)
    return ''


def reset_ip(log=print) -> bool:
    """Reboot the dongle and wait until it is back online.

    True only when it came back with a different public IP.
    """
    src = local_ip()
    if not src:
        return False
    old_ip = public_ip(src)
    why = reboot()
    if why:
        log(f'[dongle] không đổi được IP: {why}')
        return False
    log(f"[dongle] đang khởi động lại để đổi IP (IP cũ {old_ip or '?'})")
    # It drops off USB within seconds, then needs about a minute to boot and dial.
    _wait_until(lambda: not local_ip(), 45)
    new_ip = _wait_until(lambda: local_ip() and public_ip(local_ip()), _BACK_ONLINE_TIMEOUT)
    if not new_ip:
        log(f'[dongle] sau {_BACK_ONLINE_TIMEOUT} giây dongle vẫn chưa online lại')
        return False
    log(f'[dongle] online lại với IP {new_ip}')
    return new_ip != old_ip


def _main():
    ip = local_ip()
    print(f'Dongle ({DONGLE_HOST}):', f'đang cắm, IP máy {ip}' if ip else 'không thấy')
    if not ip:
        return
    print('Firmware HiMI 4G UFI:', 'đúng' if is_dongle() else 'KHÔNG phải')
    print('IP public qua dongle:', public_ip(ip) or '?')
    print('DONGLE_PASSWORD:', 'đã điền' if DONGLE_PASSWORD else 'chưa điền (tool sẽ không tự reset)')
    if '--reset' in sys.argv:
        print('Kết quả:', 'đã đổi IP' if reset_ip() else 'không đổi được IP')


if __name__ == '__main__':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
    _main()
