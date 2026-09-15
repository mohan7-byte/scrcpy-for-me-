#!/usr/bin/env python3
from pathlib import Path

ROOT = Path('upstream')

def replace_once(path: str, old: str, new: str) -> None:
    p = ROOT / path
    text = p.read_text(encoding='utf-8')
    n = text.count(old)
    if n != 1:
        raise RuntimeError(f'{path}: expected exactly 1 match, found {n}')
    p.write_text(text.replace(old, new), encoding='utf-8')

# Replace the v2 display-power implementation with the actual upstream scrcpy
# SurfaceControl/physical-display method selection.
content = r'''package org.server.scrcpy.wrappers;

import android.os.Build;
import android.os.IBinder;

import java.lang.reflect.Method;

public final class DisplayPower {
    private static final int POWER_MODE_OFF = 0;
    private static final int POWER_MODE_NORMAL = 2;

    private static final Object LOCK = new Object();
    private static volatile boolean keepActive;
    private static Thread keepActiveThread;

    private DisplayPower() {}

    public static boolean setMainDisplayPower(boolean on) {
        final int mode = on ? POWER_MODE_NORMAL : POWER_MODE_OFF;

        // Android 15+: keep this available as an optional path, but older
        // scrcpy releases reverted this mechanism because of regressions.
        if (Build.VERSION.SDK_INT >= 35) {
            if (runDisplayCommand(on ? "power-on" : "power-off")) {
                if (on) stopKeepActive(); else startKeepActive();
                return true;
            }
        }

        // Use the physical-display path on Android 10-13, matching upstream
        // scrcpy's Device.setDisplayPower() implementation.
        if (Build.VERSION.SDK_INT >= 29) {
            try {
                Class<?> sc = Class.forName("android.view.SurfaceControl");
                Method getIds = sc.getMethod("getPhysicalDisplayIds");
                Method getToken = sc.getMethod("getPhysicalDisplayToken", long.class);
                Method setPower = sc.getMethod("setDisplayPowerMode", IBinder.class, int.class);
                long[] ids = (long[]) getIds.invoke(null);
                if (ids != null && ids.length > 0) {
                    boolean ok = true;
                    for (long id : ids) {
                        IBinder token = (IBinder) getToken.invoke(null, id);
                        if (token == null) {
                            ok = false;
                            continue;
                        }
                        ok &= (Boolean) setPower.invoke(null, token, mode);
                    }
                    if (ok) {
                        if (on) stopKeepActive(); else startKeepActive();
                        return true;
                    }
                }
            } catch (Throwable ignored) {
            }
        }

        // Android 14 may move the methods behind DisplayControl. The helper
        // process used by modern scrcpy is not available in this old fork, so
        // keep this as a best-effort reflective fallback.
        if (Build.VERSION.SDK_INT >= 34) {
            try {
                Class<?> dc = Class.forName("com.android.server.display.DisplayControl");
                Method getIds = dc.getMethod("getPhysicalDisplayIds");
                Method getToken = dc.getMethod("getPhysicalDisplayToken", long.class);
                Class<?> sc = Class.forName("android.view.SurfaceControl");
                Method setPower = sc.getMethod("setDisplayPowerMode", IBinder.class, int.class);
                long[] ids = (long[]) getIds.invoke(null);
                if (ids != null && ids.length > 0) {
                    boolean ok = true;
                    for (long id : ids) {
                        IBinder token = (IBinder) getToken.invoke(null, id);
                        if (token == null) {
                            ok = false;
                            continue;
                        }
                        ok &= (Boolean) setPower.invoke(null, token, mode);
                    }
                    if (ok) {
                        if (on) stopKeepActive(); else startKeepActive();
                        return true;
                    }
                }
            } catch (Throwable ignored) {
            }
        }

        // Pre-Android-10 fallback.
        if (Build.VERSION.SDK_INT < 29) {
            try {
                Class<?> sc = Class.forName("android.view.SurfaceControl");
                Method getBuiltIn = sc.getMethod("getBuiltInDisplay", int.class);
                Method setPower = sc.getMethod("setDisplayPowerMode", IBinder.class, int.class);
                IBinder token = (IBinder) getBuiltIn.invoke(null, 0);
                if (token != null) {
                    boolean ok = (Boolean) setPower.invoke(null, token, mode);
                    if (on) stopKeepActive(); else if (ok) startKeepActive();
                    return ok;
                }
            } catch (Throwable ignored) {
            }
        }

        if (on) stopKeepActive();
        return false;
    }

    private static boolean runDisplayCommand(String command) {
        try {
            Process process = new ProcessBuilder("cmd", "display", command, "0")
                    .redirectErrorStream(true)
                    .start();
            return process.waitFor() == 0;
        } catch (Throwable ignored) {
            return false;
        }
    }

    private static void startKeepActive() {
        synchronized (LOCK) {
            if (keepActive) return;
            keepActive = true;
            keepActiveThread = new Thread(() -> {
                while (keepActive) {
                    try {
                        signalUserActivity();
                        Thread.sleep(2000);
                    } catch (InterruptedException ignored) {
                    } catch (Throwable ignored) {
                    }
                }
            }, "scrcpy-keep-active");
            keepActiveThread.setDaemon(true);
            keepActiveThread.start();
        }
    }

    private static void stopKeepActive() {
        synchronized (LOCK) {
            keepActive = false;
            if (keepActiveThread != null) {
                keepActiveThread.interrupt();
                keepActiveThread = null;
            }
        }
    }

    private static void signalUserActivity() {
        try {
            Class<?> sm = Class.forName("org.server.scrcpy.wrappers.ServiceManager");
            Method getPowerManager = sm.getDeclaredMethod("getPowerManager");
            getPowerManager.setAccessible(true);
            Object powerManager = getPowerManager.invoke(null);
            if (powerManager == null) return;
            Method method = null;
            for (Method m : powerManager.getClass().getMethods()) {
                if (m.getName().equals("userActivity") && m.getParameterTypes().length == 3) {
                    method = m;
                    break;
                }
            }
            if (method != null) {
                method.invoke(powerManager, android.os.SystemClock.uptimeMillis(), 0, 0);
            }
        } catch (Throwable ignored) {
        }
    }
}
'''

path = ROOT / 'server/src/main/java/org/server/scrcpy/wrappers/DisplayPower.java'
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(content, encoding='utf-8')

# Critical fix for this fork: when the physical panel is intentionally off,
# its legacy EventController logic otherwise interprets touch ACTION_UP as a
# wake/power gesture and stops forwarding normal touch events.
event_path = ROOT / 'server/src/main/java/org/server/scrcpy/EventController.java'
event = event_path.read_text(encoding='utf-8')
needle = '    private boolean proximity = false;\n'
if event.count(needle) != 1:
    raise RuntimeError('EventController: proximity field not found exactly once')
event = event.replace(needle, needle + '    private boolean physicalDisplayOff = false;\n', 1)

old_condition = '            if (action == MotionEvent.ACTION_UP && (!device.isScreenOn() || proximity)) {'
if event.count(old_condition) != 1:
    raise RuntimeError('EventController: legacy screen-off touch condition not found exactly once')
event = event.replace(old_condition, '            if (action == MotionEvent.ACTION_UP && (!physicalDisplayOff && (!device.isScreenOn() || proximity))) {', 1)

old_off = '''            } else if (buffer[0] == COMMAND_SCREEN_OFF) {\n                if (!org.server.scrcpy.wrappers.DisplayPower.setMainDisplayPower(false)) {\n                    Ln.w("Could not power off the physical display");\n                }\n'''
new_off = '''            } else if (buffer[0] == COMMAND_SCREEN_OFF) {\n                if (org.server.scrcpy.wrappers.DisplayPower.setMainDisplayPower(false)) {\n                    physicalDisplayOff = true;\n                } else {\n                    Ln.w("Could not power off the physical display");\n                }\n'''
if event.count(old_off) != 1:
    raise RuntimeError('EventController: screen-off branch not found exactly once')
event = event.replace(old_off, new_off, 1)

old_on = '''            } else if (buffer[0] == COMMAND_SCREEN_ON) {\n                if (!org.server.scrcpy.wrappers.DisplayPower.setMainDisplayPower(true)) {\n                    Ln.w("Could not power on the physical display");\n                }\n'''
new_on = '''            } else if (buffer[0] == COMMAND_SCREEN_ON) {\n                if (org.server.scrcpy.wrappers.DisplayPower.setMainDisplayPower(true)) {\n                    physicalDisplayOff = false;\n                } else {\n                    Ln.w("Could not power on the physical display");\n                }\n'''
if event.count(old_on) != 1:
    raise RuntimeError('EventController: screen-on branch not found exactly once')
event = event.replace(old_on, new_on, 1)
event_path.write_text(event, encoding='utf-8')
print('screen-off v4 applied: Android 10 physical-display path + touch-forwarding fix')
