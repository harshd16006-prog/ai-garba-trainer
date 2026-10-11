# AI Garba Trainer - Flutter module (plug-in folder)

Ye ek **self-contained folder** hai: `lib/garba_ai/`. Isme camera, server se baat,
score, tips aur report sab hai. Isko kisi bhi Flutter app me copy karke chala sakte ho.

```
lib/
  main.dart                        <- sirf akele test ke liye (merge me COPY MAT KARNA)
  garba_ai/                        <- ye poora folder app me jayega
    garba_ai.dart                  (import yahi karna hai)
    garba_ai_trainer_screen.dart   (camera + live score + tips)
    garba_ai_report_screen.dart    (performance report)
    garba_ai_api.dart              (Python server se baat)
    garba_ai_config.dart           (server ka default address)
```

Saare class naam `GarbaAi...` se shuru hote hain, to tumhari existing app ke
naamon se nahi takrayenge. Folder ke andar sab imports relative hain, to folder
ka location badalne par bhi kaam karega.

---

## A) Pehle akele test karo (abhi karna hai)

1. Naya project: `flutter create garba_test` aur `cd garba_test`
2. `flutter pub add camera http`
3. Is zip ka `lib/` folder us project ke `lib/` me daalo (main.dart replace hone do).
4. `lib/garba_ai/garba_ai_config.dart` me apne laptop ka IP daalo (ya app ke andar
   upar wale icon se baad me bhi daal sakte ho).
5. Android permissions (neeche "Permissions" section).
6. Laptop par `python api_server.py` chalao, phone USB se lagao, `flutter run`.

## B) Existing Garba app me integrate (baad me)

1. **Folder copy:** `lib/garba_ai/` ko apni app ke `lib/` me copy karo.
   (`main.dart` copy mat karna.)
2. **Packages:** app ke folder me `flutter pub add camera http`
   (agar already hain to skip).
3. **Permissions:** neeche wale section se apne `AndroidManifest.xml` me merge karo.
   `minSdk` 24 ya usse upar.
4. **Ek button / menu item** jahan se AI trainer kholna hai:
```dart
import 'garba_ai/garba_ai.dart';   // file ke upar

// button ke onPressed me:
Navigator.push(context,
  MaterialPageRoute(builder: (_) => const GarbaAiTrainerScreen()));
```
5. `flutter build apk --release` -> naya APK banega.

Agar app GetX / go_router / named routes use karti hai, to bas wahi apna navigation
use karke `const GarbaAiTrainerScreen()` ko screen ki tarah kholo. Module ko aur
kuch nahi chahiye.

## Permissions (Android)

`android/app/src/main/AndroidManifest.xml`, `<application` ke **upar**:
```xml
<uses-permission android:name="android.permission.CAMERA"/>
<uses-permission android:name="android.permission.INTERNET"/>
```
`<application` tag ke andar:
```xml
android:usesCleartextTraffic="true"
```
`android/app/build.gradle(.kts)` me `minSdk = 24`.

## Server address

- Default: `lib/garba_ai/garba_ai_config.dart`.
- App ke andar: camera screen ke upar **settings_ethernet icon** -> naya address ->
  "Save & test". Isse APK dobara banane ki zaroorat nahi.
- Code se bhi de sakte ho: `GarbaAiTrainerScreen(serverUrl: 'http://192.168.1.7:8000')`.

## Ye module kya MAANTA hai

- Laptop par `api_server.py` chal raha ho aur phone usi Wi-Fi par ho.
- Ye module alag se camera kholta hai, to app me kahin aur `availableCameras()`
  pehle se call karna zaroori nahi.
- Left/right ulte lagein to camera screen ke upar **cameraswitch icon** se camera badlo.

## Limit

Ye client-server design hai: APK ke andar sirf screen hai, AI laptop par chalta hai.
Server band ho to app "Cannot reach AI server" dikhayegi.
