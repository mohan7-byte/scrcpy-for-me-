#!/usr/bin/env python3
from pathlib import Path
ROOT = Path('upstream')

def replace(path, old, new, count=1):
    p = ROOT / path
    s = p.read_text(encoding='utf-8')
    n = s.count(old)
    if n != count:
        raise RuntimeError(f'{path}: expected {count} matches, found {n}')
    p.write_text(s.replace(old, new, count), encoding='utf-8')

# Dedicated screen-power command, separate from key events.
for path in [
    'app/src/main/java/org/client/scrcpy/model/CommandPacket.java',
    'server/src/main/java/org/server/scrcpy/model/CommandPacket.java',
]:
    replace(path,
            'JSON_EXTRA_CMD((byte) 0), VIDEO_NEW_KEY_FRAME((byte) 1);',
            'JSON_EXTRA_CMD((byte) 0), VIDEO_NEW_KEY_FRAME((byte) 1), SCREEN_POWER((byte) 2);')

# Client: send a real command packet with one byte: 0 = off, 1 = on.
replace('app/src/main/java/org/client/scrcpy/Scrcpy.java',
        '    public void sendKeyevent(int keycode) {',
        '''    public void sendDisplayPower(boolean on) {\n        if (!LetServceRunning.get() || socketOutputStream == null) {\n            return;\n        }\n        try {\n            socketOutputStream.write(CommandPacket.toArray(\n                    MediaPacket.Type.COMMAND,\n                    CommandPacket.CmdType.SCREEN_POWER,\n                    new byte[]{(byte) (on ? 1 : 0)}));\n            socketOutputStream.flush();\n        } catch (IOException e) {\n            Log.e("Scrcpy", "Could not request display power", e);\n        }\n    }\n\n    public void sendKeyevent(int keycode) {''')

replace('app/src/main/java/org/client/scrcpy/ScrcpyHost.java',
        '    public void screenOff() {\n        if (scrcpy != null) scrcpy.sendKeyevent(COMMAND_SCREEN_OFF);\n    }\n\n    public void screenOn() {\n        if (scrcpy != null) scrcpy.sendKeyevent(COMMAND_SCREEN_ON);\n    }',
        '''    public void screenOff() {\n        if (scrcpy != null) scrcpy.sendDisplayPower(false);\n    }\n\n    public void screenOn() {\n        if (scrcpy != null) scrcpy.sendDisplayPower(true);\n    }''')

# Remove the old sentinel key constants from ScrcpyHost.
replace('app/src/main/java/org/client/scrcpy/ScrcpyHost.java',
        '    private static final int COMMAND_SCREEN_OFF = -10001;\n    private static final int COMMAND_SCREEN_ON = -10002;\n\n',
        '')

# Server command dispatch. Keep old VIDEO_NEW_KEY_FRAME untouched.
replace('server/src/main/java/org/server/scrcpy/EventController.java',
        '''            case VIDEO_NEW_KEY_FRAME:\n                screenEncoder.asyncRequestKeyFrame();\n                break;\n''',
        '''            case VIDEO_NEW_KEY_FRAME:\n                screenEncoder.asyncRequestKeyFrame();\n                break;\n            case SCREEN_POWER:\n                if (commandPacket.data == null || commandPacket.data.length < 1) {\n                    Ln.w("Invalid screen power command");\n                    break;\n                }\n                boolean on = commandPacket.data[0] != 0;\n                if (!org.server.scrcpy.wrappers.DisplayPower.setMainDisplayPower(on)) {\n                    Ln.w("Could not change physical display power");\n                }\n                break;\n''')

# Do not let the legacy ACTION_UP screen-off hack interfere with remote touch.
replace('server/src/main/java/org/server/scrcpy/EventController.java',
        '    private boolean physicalDisplayOff = false;\n', '')
replace('server/src/main/java/org/server/scrcpy/EventController.java',
        '            if (action == MotionEvent.ACTION_UP && (!physicalDisplayOff && (!device.isScreenOn() || proximity))) {',
        '            if (action == MotionEvent.ACTION_UP && proximity) {')

# Remove the old negative-keycode screen power handlers entirely.
old = '''            } else if (buffer[0] == COMMAND_SCREEN_OFF) {\n                if (org.server.scrcpy.wrappers.DisplayPower.setMainDisplayPower(false)) {\n                    physicalDisplayOff = true;\n                } else {\n                    Ln.w("Could not power off the physical display");\n                }\n            } else if (buffer[0] == COMMAND_SCREEN_ON) {\n                if (org.server.scrcpy.wrappers.DisplayPower.setMainDisplayPower(true)) {\n                    physicalDisplayOff = false;\n                } else {\n                    Ln.w("Could not power on the physical display");\n                }\n'''
replace('server/src/main/java/org/server/scrcpy/EventController.java', old, '            } else {\n', 1)
# The replacement above leaves the following generic else duplicated; normalize the exact sequence.
replace('server/src/main/java/org/server/scrcpy/EventController.java',
        '''            } else {\n            } else {\n                injectKeycode(buffer[0]);\n            }\n''',
        '''            } else {\n                injectKeycode(buffer[0]);\n            }\n''', 1)

# Upstream behavior: main display (id 0) must not be forcibly tagged.
replace('server/src/main/java/org/server/scrcpy/Device.java',
        '        if (!org.server.scrcpy.wrappers.InputManager.setDisplayId(inputEvent, displayId)) {\n            Ln.w("Could not set displayId=" + displayId + " on input event");\n        }\n',
        '''        if (displayId != 0 && !org.server.scrcpy.wrappers.InputManager.setDisplayId(inputEvent, displayId)) {\n            Ln.w("Could not set displayId=" + displayId + " on input event");\n        }\n''')

# Add the upstream-style keepActive() API to this fork's PowerManager.
replace('server/src/main/java/org/server/scrcpy/wrappers/PowerManager.java',
        '    public boolean isScreenOn() {',
        '''    public void userActivity(int displayId) {\n        try {\n            Method method;\n            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {\n                method = manager.getClass().getMethod("userActivity", int.class, long.class, int.class, int.class);\n                method.invoke(manager, displayId, android.os.SystemClock.uptimeMillis(), 0, 0);\n            } else {\n                method = manager.getClass().getMethod("userActivity", long.class, int.class, int.class);\n                method.invoke(manager, android.os.SystemClock.uptimeMillis(), 0, 0);\n            }\n        } catch (ReflectiveOperationException e) {\n            // Keep-active is best effort.\n        }\n    }\n\n    public boolean isScreenOn() {''')

# Make the existing DisplayPower keep-active call the new typed wrapper.
replace('server/src/main/java/org/server/scrcpy/wrappers/DisplayPower.java',
        '    private static void signalUserActivity() {\n        try {\n            Class<?> sm = Class.forName("org.server.scrcpy.wrappers.ServiceManager");\n            Method getPowerManager = sm.getDeclaredMethod("getPowerManager");\n            getPowerManager.setAccessible(true);\n            Object powerManager = getPowerManager.invoke(null);\n            if (powerManager == null) return;\n            Method method = null;\n            for (Method m : powerManager.getClass().getMethods()) {\n                if (m.getName().equals("userActivity") && m.getParameterTypes().length == 3) {\n                    method = m;\n                    break;\n                }\n            }\n            if (method != null) {\n                method.invoke(powerManager, android.os.SystemClock.uptimeMillis(), 0, 0);\n            }\n        } catch (Throwable ignored) {\n        }\n    }',
        '''    private static void signalUserActivity() {\n        try {\n            ServiceManager.getPowerManager().userActivity(0);\n        } catch (Throwable ignored) {\n        }\n    }''')

print('screen power protocol patch applied')
