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

# Client: add screen power commands to the existing key-event transport.
replace_once(
    'app/src/main/java/org/client/scrcpy/ScrcpyHost.java',
    'public class ScrcpyHost implements Scrcpy.ServiceCallbacks {\n\n    private Context context;',
    'public class ScrcpyHost implements Scrcpy.ServiceCallbacks {\n\n    private static final int COMMAND_SCREEN_OFF = -10001;\n    private static final int COMMAND_SCREEN_ON = -10002;\n\n    private Context context;')
replace_once(
    'app/src/main/java/org/client/scrcpy/ScrcpyHost.java',
    '    public void keyEvent(int keyCode) {\n        scrcpy.sendKeyevent(keyCode);\n    }\n\n\n    @Override',
    '    public void keyEvent(int keyCode) {\n        scrcpy.sendKeyevent(keyCode);\n    }\n\n    public void screenOff() {\n        if (scrcpy != null) scrcpy.sendKeyevent(COMMAND_SCREEN_OFF);\n    }\n\n    public void screenOn() {\n        if (scrcpy != null) scrcpy.sendKeyevent(COMMAND_SCREEN_ON);\n    }\n\n\n    @Override')

# Client: floating mirror button and state label.
replace_once(
    'app/src/main/java/org/client/scrcpy/DisplayWindow.java',
    'import android.widget.FrameLayout;\n',
    'import android.widget.FrameLayout;\nimport android.widget.TextView;\n')
replace_once(
    'app/src/main/java/org/client/scrcpy/DisplayWindow.java',
    '''        findViewById(R.id.action_menu).setOnTouchListener(new OnTouchListener() {\n            @Override\n            public boolean onTouch(View view, MotionEvent motionEvent) {\n                if (motionEvent.getActionMasked() == MotionEvent.ACTION_DOWN){\n                    actionCallback.onAction(2);\n                }\n                return false;\n            }\n        });\n''',
    '''        findViewById(R.id.action_menu).setOnTouchListener(new OnTouchListener() {\n            @Override\n            public boolean onTouch(View view, MotionEvent motionEvent) {\n                if (motionEvent.getActionMasked() == MotionEvent.ACTION_DOWN){\n                    actionCallback.onAction(2);\n                }\n                return false;\n            }\n        });\n        findViewById(R.id.action_screen_power).setOnTouchListener(new OnTouchListener() {\n            @Override\n            public boolean onTouch(View view, MotionEvent motionEvent) {\n                if (motionEvent.getActionMasked() == MotionEvent.ACTION_DOWN){\n                    actionCallback.onAction(3);\n                }\n                return false;\n            }\n        });\n''')
replace_once(
    'app/src/main/java/org/client/scrcpy/DisplayWindow.java',
    '''    public void hideHintTip(){\n        findViewById(R.id.hint).setVisibility(GONE);\n    }\n''',
    '''    public void hideHintTip(){\n        findViewById(R.id.hint).setVisibility(GONE);\n    }\n\n    public void setScreenPowerOffState(boolean off) {\n        TextView label = findViewById(R.id.action_screen_power);\n        if (label != null) label.setText(off ? "ON" : "OFF");\n    }\n''')
replace_once(
    'app/src/main/res/layout/window_display.xml',
    '''        <TextView\n            android:id="@+id/action_menu"\n            android:layout_width="0dp"\n            android:layout_height="wrap_content"\n            android:layout_weight="1"\n            android:gravity="center"\n            android:text="="\n            android:textSize="18sp" />\n''',
    '''        <TextView\n            android:id="@+id/action_menu"\n            android:layout_width="0dp"\n            android:layout_height="wrap_content"\n            android:layout_weight="1"\n            android:gravity="center"\n            android:text="="\n            android:textSize="18sp" />\n\n        <TextView\n            android:id="@+id/action_screen_power"\n            android:layout_width="0dp"\n            android:layout_height="wrap_content"\n            android:layout_weight="1"\n            android:gravity="center"\n            android:text="OFF"\n            android:textSize="14sp" />\n''')
replace_once(
    'app/src/main/java/org/client/scrcpy/FloatService.java',
    '    ScrcpyHost scrcpyHost;\n\n    int w;',
    '    ScrcpyHost scrcpyHost;\n    boolean physicalScreenOff = false;\n\n    int w;')
replace_once(
    'app/src/main/java/org/client/scrcpy/FloatService.java',
    '''                    case 2:\n                        scrcpyHost.keyEvent(187);\n                        break;\n                }\n''',
    '''                    case 2:\n                        scrcpyHost.keyEvent(187);\n                        break;\n                    case 3:\n                        physicalScreenOff = !physicalScreenOff;\n                        if (physicalScreenOff) scrcpyHost.screenOff();\n                        else scrcpyHost.screenOn();\n                        displayWindow.setScreenPowerOffState(physicalScreenOff);\n                        break;\n                }\n''')

# Server: physical display power control. Reflection avoids compile-time hidden API dependencies.
(ROOT / 'server/src/main/java/org/server/scrcpy/wrappers/DisplayPower.java').write_text('''package org.server.scrcpy.wrappers;\n\nimport android.os.IBinder;\n\nimport java.lang.reflect.Method;\n\npublic final class DisplayPower {\n    private static final int POWER_MODE_OFF = 0;\n    private static final int POWER_MODE_NORMAL = 2;\n\n    private DisplayPower() {}\n\n    public static boolean setMainDisplayPower(boolean on) {\n        int mode = on ? POWER_MODE_NORMAL : POWER_MODE_OFF;\n\n        // Older Android path.\n        try {\n            Class<?> sc = Class.forName("android.view.SurfaceControl");\n            Method getBuiltInDisplay = sc.getDeclaredMethod("getBuiltInDisplay");\n            Method setDisplayPowerMode = sc.getDeclaredMethod("setDisplayPowerMode", IBinder.class, int.class);\n            getBuiltInDisplay.setAccessible(true);\n            setDisplayPowerMode.setAccessible(true);\n            IBinder token = (IBinder) getBuiltInDisplay.invoke(null);\n            if (token != null) return (Boolean) setDisplayPowerMode.invoke(null, token, mode);\n        } catch (Throwable ignored) {}\n\n        // Android 10-13 path.\n        try {\n            Class<?> sc = Class.forName("android.view.SurfaceControl");\n            Method getIds = sc.getDeclaredMethod("getPhysicalDisplayIds");\n            Method getToken = sc.getDeclaredMethod("getPhysicalDisplayToken", long.class);\n            Method setPower = sc.getDeclaredMethod("setDisplayPowerMode", IBinder.class, int.class);\n            getIds.setAccessible(true);\n            getToken.setAccessible(true);\n            setPower.setAccessible(true);\n            long[] ids = (long[]) getIds.invoke(null);\n            if (ids != null && ids.length > 0) {\n                boolean ok = true;\n                for (long id : ids) {\n                    IBinder token = (IBinder) getToken.invoke(null, id);\n                    if (token != null) ok &= (Boolean) setPower.invoke(null, token, mode);\n                }\n                return ok;\n            }\n        } catch (Throwable ignored) {}\n\n        // Android 14+ path.\n        try {\n            Class<?> dc = Class.forName("android.hardware.display.DisplayControl");\n            Class<?> sc = Class.forName("android.view.SurfaceControl");\n            Method getIds = dc.getDeclaredMethod("getPhysicalDisplayIds");\n            Method getToken = dc.getDeclaredMethod("getPhysicalDisplayToken", long.class);\n            Method setPower = sc.getDeclaredMethod("setDisplayPowerMode", IBinder.class, int.class);\n            getIds.setAccessible(true);\n            getToken.setAccessible(true);\n            setPower.setAccessible(true);\n            long[] ids = (long[]) getIds.invoke(null);\n            if (ids != null && ids.length > 0) {\n                boolean ok = true;\n                for (long id : ids) {\n                    IBinder token = (IBinder) getToken.invoke(null, id);\n                    if (token != null) ok &= (Boolean) setPower.invoke(null, token, mode);\n                }\n                return ok;\n            }\n        } catch (Throwable ignored) {}\n\n        return false;\n    }\n}\n''', encoding='utf-8')

replace_once(
    'server/src/main/java/org/server/scrcpy/EventController.java',
    'public class EventController {\n\n    private final Device device;',
    'public class EventController {\n\n    private static final int COMMAND_SCREEN_OFF = -10001;\n    private static final int COMMAND_SCREEN_ON = -10002;\n\n    private final Device device;')
replace_once(
    'server/src/main/java/org/server/scrcpy/EventController.java',
    '''            } else {\n                injectKeycode(buffer[0]);\n            }\n''',
    '''            } else if (buffer[0] == COMMAND_SCREEN_OFF) {\n                if (!org.server.scrcpy.wrappers.DisplayPower.setMainDisplayPower(false)) {\n                    Ln.w("Could not power off the physical display");\n                }\n            } else if (buffer[0] == COMMAND_SCREEN_ON) {\n                if (!org.server.scrcpy.wrappers.DisplayPower.setMainDisplayPower(true)) {\n                    Ln.w("Could not power on the physical display");\n                }\n            } else {\n                injectKeycode(buffer[0]);\n            }\n''')

print('screen-off patch applied')
