#!/usr/bin/env python3
from pathlib import Path

ROOT = Path('upstream')

# Replace the v2 display-power implementation with the actual upstream scrcpy
# SurfaceControl method selection:
#   Android < 10: getBuiltInDisplay(0)
#   Android >= 10: getInternalDisplayToken()
# Android 15+: official `cmd display power-off/on 0` is tried first.
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

        // Android 15+: this is the official shell interface documented by scrcpy.
        if (Build.VERSION.SDK_INT >= 35) {
            if (runDisplayCommand(on ? "power-on" : "power-off")) {
                if (on) stopKeepActive(); else startKeepActive();
                return true;
            }
        }

        // Exact upstream scrcpy wrapper logic for the internal/main display.
        try {
            Class<?> sc = Class.forName("android.view.SurfaceControl");
            IBinder token;
            if (Build.VERSION.SDK_INT < 29) {
                Method method = sc.getMethod("getBuiltInDisplay", int.class);
                token = (IBinder) method.invoke(null, 0);
            } else {
                Method method = sc.getMethod("getInternalDisplayToken");
                token = (IBinder) method.invoke(null);
            }

            if (token != null) {
                Method setPower = sc.getMethod("setDisplayPowerMode", IBinder.class, int.class);
                setPower.invoke(null, token, mode);
                if (on) stopKeepActive(); else startKeepActive();
                return true;
            }
        } catch (Throwable ignored) {
        }

        // Fallback for devices exposing physical-display APIs.
        try {
            Class<?> sc = Class.forName("android.view.SurfaceControl");
            Method getIds = sc.getMethod("getPhysicalDisplayIds");
            Method getToken = sc.getMethod("getPhysicalDisplayToken", long.class);
            Method setPower = sc.getMethod("setDisplayPowerMode", IBinder.class, int.class);
            long[] ids = (long[]) getIds.invoke(null);
            if (ids != null && ids.length > 0) {
                IBinder token = (IBinder) getToken.invoke(null, ids[0]);
                if (token != null) {
                    setPower.invoke(null, token, mode);
                    if (on) stopKeepActive(); else startKeepActive();
                    return true;
                }
            }
        } catch (Throwable ignored) {
        }

        // Android 14+ fallback where physical display methods are exposed from DisplayControl.
        try {
            Class<?> dc = Class.forName("android.hardware.display.DisplayControl");
            Class<?> sc = Class.forName("android.view.SurfaceControl");
            Method getIds = dc.getMethod("getPhysicalDisplayIds");
            Method getToken = dc.getMethod("getPhysicalDisplayToken", long.class);
            Method setPower = sc.getMethod("setDisplayPowerMode", IBinder.class, int.class);
            long[] ids = (long[]) getIds.invoke(null);
            if (ids != null && ids.length > 0) {
                IBinder token = (IBinder) getToken.invoke(null, ids[0]);
                if (token != null) {
                    setPower.invoke(null, token, mode);
                    if (on) stopKeepActive(); else startKeepActive();
                    return true;
                }
            }
        } catch (Throwable ignored) {
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

    /**
     * Keep the Android system active while the physical display is blanked.
     * This mirrors the intent of scrcpy's --keep-active option and prevents
     * a device from subsequently entering a full suspended state.
     */
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
            // Call the fork's PowerManager wrapper if it exposes userActivity().
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
print('DisplayPower v3 installed')
