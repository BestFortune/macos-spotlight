"""
System commands and shortcuts for macOS Spotlight clone.
"""
import os
import subprocess
from typing import List, Dict, Any, Optional

class SystemAction:
    __slots__ = ('id', 'name', 'keywords', 'icon_name', 'description', 'command')

    def __init__(self, id: str, name: str, keywords: List[str], icon_name: str, description: str, command: str):
        self.id = id
        self.name = name
        self.keywords = keywords
        self.icon_name = icon_name
        self.description = description
        self.command = command

    def execute(self):
        try:
            subprocess.Popen(self.command, shell=True, start_new_session=True)
        except Exception:
            pass

SYSTEM_ACTIONS = [
    SystemAction(
        id='lock',
        name='Lock Screen',
        keywords=['lock', 'screen lock', 'lock screen', 'sleep display'],
        icon_name='system-lock-screen',
        description='Lock the screen immediately',
        command='cinnamon-screensaver-command -l || loginctl lock-session'
    ),
    SystemAction(
        id='sleep',
        name='Sleep / Suspend',
        keywords=['sleep', 'suspend', 'hibernate', 'standby'],
        icon_name='system-suspend',
        description='Put the computer into sleep mode',
        command='systemctl suspend'
    ),
    SystemAction(
        id='restart',
        name='Restart...',
        keywords=['restart', 'reboot', 'reset'],
        icon_name='system-reboot',
        description='Restart the computer',
        command='systemctl reboot'
    ),
    SystemAction(
        id='shutdown',
        name='Shut Down...',
        keywords=['shutdown', 'shut down', 'power off', 'poweroff', 'turn off'],
        icon_name='system-shutdown',
        description='Turn off the computer completely',
        command='systemctl poweroff'
    ),
    SystemAction(
        id='logout',
        name='Log Out...',
        keywords=['logout', 'log out', 'sign out', 'signout'],
        icon_name='system-log-out',
        description='Log out of the current desktop session',
        command='cinnamon-session-quit --logout --no-prompt || loginctl terminate-session ${XDG_SESSION_ID}'
    ),
    SystemAction(
        id='settings',
        name='System Settings',
        keywords=['settings', 'preferences', 'control center', 'system preferences'],
        icon_name='preferences-system',
        description='Open Cinnamon System Settings',
        command='cinnamon-settings'
    ),
    SystemAction(
        id='empty_trash',
        name='Empty Trash',
        keywords=['empty trash', 'trash', 'clean trash', 'delete trash', 'bin'],
        icon_name='user-trash-full',
        description='Permanently remove all items in Trash',
        command='gio trash --empty'
    ),
]

def search_system_actions(query: str) -> List[SystemAction]:
    q = query.strip().lower()
    if not q:
        return []
    matches = []
    for action in SYSTEM_ACTIONS:
        score = 0
        name_lower = action.name.lower()
        if name_lower.startswith(q):
            score = 100
        elif q in name_lower:
            score = 70
        else:
            for kw in action.keywords:
                if kw.startswith(q):
                    score = 80
                    break
                elif q in kw:
                    score = 50
                    break
        if score > 0:
            matches.append((action, score))

    matches.sort(key=lambda x: x[1], reverse=True)
    return [m[0] for m in matches]
