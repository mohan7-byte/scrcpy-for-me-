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

# Client: add dedicated screen-power commands over the existing key-event transport.
replace_once(
    'app/src/main/java/org/client/scrcpy/ScrcpyHost.java',
    'public class ScrcpyHost implements Scrcpy.ServiceCallbacks {\n\n    private Context context;',
    'public class ScrcpyHost implements Scrcpy.ServiceCallbacks {\n\n    private static final int COMMAND_SCREEN_OFF = -10001;\n    private static final int COMMAND_SCREEN_ON = -10002;\n\n    private Context context;')
replace_once(
    'app/src/main/java/org/client/scrcpy/ScrcpyHost.java',
    '    public void keyEvent(int keyCode) {\n        scrcpy.sendKeyevent(keyCode);\n    }\n\n\n    @Override',
    '    public void keyEvent(int keyCode) {\n        scrcpy.sendKeyevent(keyCode);\n    }\n\n    public void screenOff() {\n        if (scrcpy != null) scrcpy.sendKeyevent(COMMAND_SCREEN_OFF);\n    }\n\n    public void screenOn() {\n        if (scrcpy != null) scrcpy.sendKeyevent(COMMAND_SCREEN_ON);\n    }\n\n\n    @Override')

# Client: separate floating button over the video area.
replace_once(
    'app/src/main/java/org/client/scrcpy/DisplayWindow.java',
    'import android.widget.FrameLayout;\n',
    'import android.widget.FrameLayout;\nimport android.widget.TextView;\n')
replace_once(
    'app/src/main/java/org/client/scrcpy/DisplayWindow.java',
    '''        findViewById(R.id.action_menu).setOnTouchListener(new OnTouchListener() {\n            @Override\n            public boolean onTouch(View view, MotionEvent motionEvent) {\n                if (motionEvent.getActionMasked() == MotionEvent.ACTION_DOWN){\n                    actionCallback.onAction(2);\n                }\n                return false;\n            }\n        });\n''',
    '''        findViewById(R.id.action_menu).setOnTouchListener(new OnTouchListener() {\n            @Override\n            public boolean onTouch(View view, MotionEvent motionEvent) {\n                if (motionEvent.getActionMasked() == MotionEvent.ACTION_DOWN){\n                    actionCallback.onAction(2);\n                }\n                return false;\n            }\n        });\n        findViewById(R.id/screen_power_fab).setOnTouchListener(new OnTouchListener() {\n            @Override\n            public boolean onTouch(View view, MotionEvent motionEvent) {\n                if (motionEvent.getActionMasked() == MotionEvent.ACTION_DOWN){\n                    actionCallback.onAction(3);\n                }\n                return true;\n            }\n        });\n'''.replace('R.id/screen_power_fab','R.id.screen_power_fab'))
replace_once(
    'app/src/main/java/org/client/scrcpy/DisplayWindow.java',
    '''    public void hideHintTip(){\n        findViewById(R.id.hint).setVisibility(GONE);\n    }\n''',
    '''    public void hideHintTip(){\n        findViewById(R.id.hint).setVisibility(GONE);\n    }\n\n    public void setScreenPowerOffState(boolean off) {\n        TextView label = findViewById(R.id.screen_power_fab);\n        if (label != null) label.setText(off ? "ON" : "OFF");\n    }\n''')
replace_once(
    'app/src/main/res/layout/window_display.xml',
    '''        <TextView\n            android:id="@+id/hint"\n            android:layout_width="match_parent"\n            android:layout_height="match_parent"\n            android:gravity="center"\n            android:text="链接中...30秒没反应估计就挂了\\n\\n注意手机提示配对的弹窗"\n            android:textColor="@color/white" />\n    </FrameLayout>\n''',
    '''        <TextView\n            android:id="@+id/hint"\n            android:layout_width="match_parent"\n            android:layout_height="match_parent"\n            android:gravity="center"\n            android:text="链接中...30秒没反应估计就挂了\\n\\n注意手机提示配对的弹窗"\n            android:textColor="@color/white" />\n\n        <TextView\n            android:id="@+id/screen_power_fab"\n            android:layout_width="48dp"\n            android:layout_height="40dp"\n            android:layout_gravity="bottom|end"\n            android:layout_marginEnd="6dp"\n            android:layout_marginBottom="6dp"\n            android:background="@android:drawable/btn_default"\n            android:clickable="true"\n            android:focusable="true"\n            android:gravity="center"\n            android:text="OFF"\n            android:textColor="@color/black"\n            android:textSize="12sp"\n            android:elevation="8dp" />\n    </FrameLayout>\n''')

# Client: toggle state, and restore the physical display when the service closes.
replace_once(
    'app/src/main/java/org/client/scrcpy/FloatService.java',
    '    ScrcpyHost scrcpyHost;\n\n    int w;',
    '    ScrcpyHost scrcpyHost;\n    boolean physicalScreenOff = false;\n\n    int w;')
replace_once(
    'app/src/main/java/org/client/scrcpy/FloatService.java',
    '''        scrcpyHost.destroy();\n        System.exit(0);\n''',
    '''        if (physicalScreenOff && scrcpyHost != null) {\n            scrcpyHost.screenOn();\n        }\n        if (scrcpyHost != null) {\n            scrcpyHost.destroy();\n        }\n        System.exit(0);\n''')
replace_once(
    'app/src/main/java/org/client/scrcpy/FloatService.java',
    '''                    case 2:\n                        scrcpyHost.keyEvent(187);\n                        break;\n                }\n''',
    '''                    case 2:\n                        scrcpyHost.keyEvent(187);\n                        break;\n                    case 3:\n                        physicalScreenOff = !physicalScreenOff;\n                        if (physicalScreenOff) {\n                            scrcpyHost.screenOff();\n                        } else {\n                            scrcpyHost.screenOn();\n                        }\n                        displayWindow.setScreenPowerOffState(physicalScreenOff);\n                        break;\n                }\n''')

# Server: prefer Android 15+ official display power command; fallback to SurfaceControl.
(ROOT / 'server/src/main/java/org/server/scrcpy/wrappers/DisplayPower.java').write_text(r'''package org.server.scrcpy.wrappers;

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
        if (!on) {
            if (runDisplayCommand("power-off")) {
                startKeepActive();
                return true;
            }
        } else {
            stopKeepActive();
            if (runDisplayCommand("power-on")) {
                return true;
            }
        }

        int mode = on ? POWER_MODE_NORMAL : POWER_MODE_OFF;

        try {
            Class<?> sc = Class.forName("android.view.SurfaceControl");
            Method getBuiltInDisplay = sc.getDeclaredMethod("getBuiltInDisplay");
            Method setDisplayPowerMode = sc.getDeclaredMethod("setDisplayPowerMode", IBinder.class, int.class);
            getBuiltInDisplay.setAccessible(true);
            setDisplayPowerMode.setAccessible(true);
            IBinder token = (IBinder) getBuiltInDisplay.invoke(null);
            if (token != null) {
                boolean ok = (Boolean) setDisplayPowerMode.invoke(null, token, mode);
                if (!on && ok) startKeepActive();
                return ok;
            }
        } catch (Throwable ignored) {}

        try {
            Class<?> sc = Class.forName("android.view.SurfaceControl");
            Method getIds = sc.getDeclaredMethod("getPhysicalDisplayIds");
            Method getToken = sc.getDeclaredMethod("getPhysicalDisplayToken", long.class);
            Method setPower = sc.getDeclaredMethod("setDisplayPowerMode", IBinder.class, int.class);
            getIds.setAccessible(true);
            getToken.setAccessible(true);
            setPower.setAccessible(true);
            long[] ids = (long[]) getIds.invoke(null);
            if (ids != null && ids.length > 0) {
                boolean ok = true;
                for (long id : ids) {
                    IBinder token = (IBinder) getToken.invoke(null, id);
                    if (token != null) ok &= (Boolean) setPower.invoke(null, token, mode);
                }
                if (!on && ok) startKeepActive();
                return ok;
            }
        } catch (Throwable ignored) {}

        try {
            Class<?> dc = Class.forName("android.hardware.display.DisplayControl");
            Class<?> sc = Class.forName("android.view.SurfaceControl");
            Method getIds = dc.getDeclaredMethod("getPhysicalDisplayIds");
            Method getToken = dc.getDeclaredMethod("getPhysicalDisplayToken", long.class);
            Method setPower = sc.getDeclaredMethod("setDisplayPowerMode", IBinder.class, int.class);
            getIds.setAccessible(true);
            getToken.setAccessible(true);
            setPower.setAccessible(true);
            long[] ids = (long[]) getIds.invoke(null);
            if (ids != null && ids.length > 0) {
                boolean ok = true;
                for (long id : ids) {
                    IBinder token = (IBinder) getToken.invoke(null, id);
                    if (token != null) ok &= (Boolean) setPower.invoke(null, token, mode);
                }
                if (!on && ok) startKeepActive();
                return ok;
            }
        } catch (Throwable ignored) {}

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
            Method userActivity = powerManager.getClass().getDeclaredMethod(
                    "userActivity", long.class, int.class, int.class);
            userActivity.setAccessible(true);
            userActivity.invoke(powerManager, System.currentTimeMillis(), 0, 0);
        } catch (Throwable ignored) {
        }
    }
}
''', encoding='utf-8')

replace_once(
    'server/src/main/java/org/server/scrcpy/EventController.java',
    'public class EventController {\n\n    private final Device device;',
    'public class EventController {\n\n    private static final int COMMAND_SCREEN_OFF = -10001;\n    private static final int COMMAND_SCREEN_ON = -10002;\n\n    private final Device device;')
replace_once(
    'server/src/main/java/org/server/scrcpy/EventController.java',
    '''            } else {\n                injectKeycode(buffer[0]);\n            }\n''',
    '''            } else if (buffer[0] == COMMAND_SCREEN_OFF) {\n                if (!org.server.scrcpy.wrappers.DisplayPower.setMainDisplayPower(false)) {\n                    Ln.w("Could not power off the physical display");\n                }\n            } else if (buffer[0] == COMMAND_SCREEN_ON) {\n                if (!org.server.scrcpy.wrappers.DisplayPower.setMainDisplayPower(true)) {\n                    Ln.w("Could not power on the physical display");\n                }\n            } else {\n                injectKeycode(buffer[0]);\n            }\n''')

print('screen-off patch v2 applied')
