// lib/garba_ai/garba_ai_config.dart
// ONE place for settings. Change the default address here, or change it
// inside the app (settings icon on the camera screen) without rebuilding.

class GarbaAiConfig {
  /// Address of the computer running api_server.py (NOT localhost).
  /// Find it on Windows with `ipconfig`, on Mac with `ipconfig getifaddr en0`.
  static String serverUrl = 'http://192.168.1.5:8000';
}
