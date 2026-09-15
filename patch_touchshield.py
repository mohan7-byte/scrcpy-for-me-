#!/usr/bin/env python3
from pathlib import Path
ROOT = Path('upstream')

def replace(path, old, new, count=1):
    p = ROOT / path
    s = p.read_text(encoding='utf-8')
    n = s.count(old)
    if n < count:
        raise RuntimeError(f'{path}: expected at least {count} matches, found {n}')
    p.write_text(s.replace(old, new, count), encoding='utf-8')

# Prevent ghost touches from a physically damaged touchscreen while keeping
# scrcpy-injected MotionEvents working. This is separate from display power.
replace(
    'server/src/main/java/org/server/scrcpy/wrappers/DisplayPower.java',
    'import android.os.IBinder;\n\nimport java.lang.reflect.Method;\n',
    'import android.os.IBinder;\nimport android.util.Log;\nimport android.view.InputDevice;\n\nimport java.lang.reflect.Method;\nimport java.util.ArrayList;\nimport java.util.List;\n'
)
replace(
    'server/src/main/java/org/server/scrcpy/wrappers/DisplayPower.java',
    '    private static Thread keepActiveThread;\n',
    '    private static Thread keepActiveThread;\n    private static final List<Integer> disabledTouchDevices = new ArrayList<>();\n'
)

method_marker = '    private static boolean runDisplayCommand(String command) {\n'
methods = '''    private static void disablePhysicalTouchscreen() {\n        synchronized (disabledTouchDevices) {\n            if (!disabledTouchDevices.isEmpty()) return;\n            try {\n                for (int id : InputDevice.getDeviceIds()) {\n                    InputDevice device = InputDevice.getDevice(id);\n                    if (device == null || device.isVirtual()) continue;\n                    if ((device.getSources() & InputDevice.SOURCE_TOUCHSCREEN) == InputDevice.SOURCE_TOUCHSCREEN) {\n                        try {\n                            device.disable();\n                            disabledTouchDevices.add(id);\n                            Log.i("Scrcpy", "Disabled touchscreen device id=" + id + " name=" + device.getName());\n                        } catch (Throwable t) {\n                            Log.w("Scrcpy", "Could not disable touchscreen device id=" + id, t);\n                        }\n                    }\n                }\n            } catch (Throwable t) {\n                Log.w("Scrcpy", "Touchscreen shield unavailable", t);\n            }\n        }\n    }\n\n    private static void enablePhysicalTouchscreen() {\n        synchronized (disabledTouchDevices) {\n            for (Integer id : new ArrayList<>(disabledTouchDevices)) {\n                try {\n                    InputDevice device = InputDevice.getDevice(id);\n                    if (device != null) device.enable();\n                } catch (Throwable t) {\n                    Log.w("Scrcpy", "Could not re-enable touchscreen device id=" + id, t);\n                }\n            }\n            disabledTouchDevices.clear();\n        }\n    }\n\n'''
replace('server/src/main/java/org/server/scrcpy/wrappers/DisplayPower.java', method_marker, methods + method_marker)

# Hook the successful paths. Match at most once per source shape; other branches
# are handled by the more-indented variants below.
replace('server/src/main/java/org/server/scrcpy/wrappers/DisplayPower.java',
        '                if (on) stopKeepActive(); else startKeepActive();\n                return true;\n',
        '                if (on) { enablePhysicalTouchscreen(); stopKeepActive(); } else { disablePhysicalTouchscreen(); startKeepActive(); }\n                return true;\n', 1)
replace('server/src/main/java/org/server/scrcpy/wrappers/DisplayPower.java',
        '                        if (on) stopKeepActive(); else startKeepActive();\n                        return true;\n',
        '                        if (on) { enablePhysicalTouchscreen(); stopKeepActive(); } else { disablePhysicalTouchscreen(); startKeepActive(); }\n                        return true;\n', 1)
replace('server/src/main/java/org/server/scrcpy/wrappers/DisplayPower.java',
        '                    if (on) stopKeepActive(); else if (ok) startKeepActive();\n                    return ok;\n',
        '                    if (ok) { if (on) { enablePhysicalTouchscreen(); stopKeepActive(); } else { disablePhysicalTouchscreen(); startKeepActive(); } }\n                    return ok;\n', 1)

replace('server/src/main/java/org/server/scrcpy/wrappers/DisplayPower.java',
        '    private static void stopKeepActive() {\n',
        '    public static void restorePhysicalTouchscreen() { enablePhysicalTouchscreen(); }\n\n    private static void stopKeepActive() {\n')

print('touchscreen shield applied')
