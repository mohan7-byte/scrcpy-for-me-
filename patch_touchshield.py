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

# Prevent ghost touches from a physically damaged touchscreen while keeping
# scrcpy-injected MotionEvents working. This is intentionally separate from
# display power: the display can be off while the Android input dispatcher
# still accepts injected events.
replace(
    'server/src/main/java/org/server/scrcpy/wrappers/DisplayPower.java',
    'import android.os.IBinder;\n\nimport java.lang.reflect.Method;\n',
    'import android.os.IBinder;\nimport android.util.Log;\nimport android.view.InputDevice;\n\nimport java.lang.reflect.Method;\nimport java.util.ArrayList;\nimport java.util.List;\n'
)

insert_after = '    private static Thread keepActiveThread;\n'
shield_fields = '''    private static final List<Integer> disabledTouchDevices = new ArrayList<>();\n'''
replace('server/src/main/java/org/server/scrcpy/wrappers/DisplayPower.java', insert_after, insert_after + shield_fields)

method_marker = '    private static boolean runDisplayCommand(String command) {\n'
methods = '''    private static void disablePhysicalTouchscreen() {\n        synchronized (disabledTouchDevices) {\n            if (!disabledTouchDevices.isEmpty()) {\n                return;\n            }\n            try {\n                for (int id : InputDevice.getDeviceIds()) {\n                    InputDevice device = InputDevice.getDevice(id);\n                    if (device == null || device.isVirtual()) {\n                        continue;\n                    }\n                    if ((device.getSources() & InputDevice.SOURCE_TOUCHSCREEN) == InputDevice.SOURCE_TOUCHSCREEN) {\n                        try {\n                            device.disable();\n                            disabledTouchDevices.add(id);\n                            Log.i("Scrcpy", "Disabled physical touchscreen input device id=" + id + " name=" + device.getName());\n                        } catch (Throwable t) {\n                            Log.w("Scrcpy", "Could not disable touchscreen device id=" + id, t);\n                        }\n                    }\n                }\n            } catch (Throwable t) {\n                Log.w("Scrcpy", "Touchscreen shield unavailable", t);\n            }\n        }\n    }\n\n    private static void enablePhysicalTouchscreen() {\n        synchronized (disabledTouchDevices) {\n            for (Integer id : new ArrayList<>(disabledTouchDevices)) {\n                try {\n                    InputDevice device = InputDevice.getDevice(id);\n                    if (device != null) {\n                        device.enable();\n                        Log.i("Scrcpy", "Re-enabled physical touchscreen input device id=" + id);\n                    }\n                } catch (Throwable t) {\n                    Log.w("Scrcpy", "Could not re-enable touchscreen device id=" + id, t);\n                }\n            }\n            disabledTouchDevices.clear();\n        }\n    }\n\n'''
replace('server/src/main/java/org/server/scrcpy/wrappers/DisplayPower.java', method_marker, methods + method_marker)

# Hook the shield into every successful OFF/ON path.
replace('server/src/main/java/org/server/scrcpy/wrappers/DisplayPower.java',
        '                if (on) stopKeepActive(); else startKeepActive();\n                return true;\n',
        '                if (on) { enablePhysicalTouchscreen(); stopKeepActive(); } else { disablePhysicalTouchscreen(); startKeepActive(); }\n                return true;\n',
        count=1)
replace('server/src/main/java/org/server/scrcpy/wrappers/DisplayPower.java',
        '                        if (on) stopKeepActive(); else startKeepActive();\n                        return true;\n',
        '                        if (on) { enablePhysicalTouchscreen(); stopKeepActive(); } else { disablePhysicalTouchscreen(); startKeepActive(); }\n                        return true;\n',
        count=1)
replace('server/src/main/java/org/server/scrcpy/wrappers/DisplayPower.java',
        '                    if (on) stopKeepActive(); else if (ok) startKeepActive();\n                    return ok;\n',
        '                    if (ok) { if (on) { enablePhysicalTouchscreen(); stopKeepActive(); } else { disablePhysicalTouchscreen(); startKeepActive(); } }\n                    return ok;\n',
        count=1)

# Always restore the touchscreen if the server process is shutting down and the
# feature had disabled it. This keeps the device recoverable.
replace('server/src/main/java/org/server/scrcpy/wrappers/DisplayPower.java',
        '    private static void stopKeepActive() {\n',
        '    public static void restorePhysicalTouchscreen() { enablePhysicalTouchscreen(); }\n\n    private static void stopKeepActive() {\n')

print('touchscreen shield applied')
