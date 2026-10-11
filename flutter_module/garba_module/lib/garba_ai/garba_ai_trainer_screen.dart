// lib/garba_ai/garba_ai_trainer_screen.dart
// THE screen of the AI module. Self-contained: it opens the camera itself,
// talks to the Python server, shows score + live corrections, then the report.
//
// Use it from anywhere in an app:
//   Navigator.push(context,
//     MaterialPageRoute(builder: (_) => const GarbaAiTrainerScreen()));
import 'dart:async';
import 'package:camera/camera.dart';
import 'package:flutter/material.dart';
import 'package:flutter_tts/flutter_tts.dart';
import 'garba_ai_api.dart';
import 'garba_ai_config.dart';
import 'garba_ai_report_screen.dart';

class GarbaAiTrainerScreen extends StatefulWidget {
  const GarbaAiTrainerScreen({super.key, this.serverUrl});

  /// Optional. If null, GarbaAiConfig.serverUrl is used.
  final String? serverUrl;

  @override
  State<GarbaAiTrainerScreen> createState() => _GarbaAiTrainerScreenState();
}

class _GarbaAiTrainerScreenState extends State<GarbaAiTrainerScreen> {
  late GarbaAiApi _api;
  List<CameraDescription> _cams = [];
  int _camIndex = 0;
  CameraController? _controller;
  GarbaAiResult? _result;
  String? _error;
  bool _running = false;

  // ---- voice guidance (English / Hindi / Gujarati) ----
  final FlutterTts _tts = FlutterTts();
  String _lang = 'en';
  bool _voiceOn = true;
  String _lastSpoken = '';
  DateTime _lastSpokenAt = DateTime.fromMillisecondsSinceEpoch(0);
  static const _ttsCodes = {'en': 'en-IN', 'hi': 'hi-IN', 'gu': 'gu-IN'};
  static const _langNames = {'en': 'English', 'hi': 'हिन्दी', 'gu': 'ગુજરાતી'};

  @override
  void initState() {
    super.initState();
    _api = GarbaAiApi(widget.serverUrl ?? GarbaAiConfig.serverUrl);
    _initCameras();
    _tts.setLanguage(_ttsCodes[_lang]!);
    _tts.setSpeechRate(0.45);
  }

  // ---------- voice ----------
  List<String> _tipsFor(GarbaAiResult? r) {
    if (r == null) return const [];
    final t = r.tipsI18n[_lang];
    return (t != null && t.isNotEmpty) ? t : r.tips;
  }

  Future<void> _setLang(String lang) async {
    setState(() => _lang = lang);
    _lastSpoken = '';
    try {
      await _tts.setLanguage(_ttsCodes[lang]!);
      final ok = await _tts.isLanguageAvailable(_ttsCodes[lang]!);
      if (!(ok == true || ok == 1) && mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
            content: Text('${_langNames[lang]} voice is not installed on this '
                'phone. Settings > Text-to-speech > install it. Tips will still '
                'show as text.')));
      }
    } catch (_) {}
  }

  void _maybeSpeak(List<String> tips) {
    if (!_voiceOn || tips.isEmpty) return;
    final text = tips.join('. ');
    final gap = DateTime.now().difference(_lastSpokenAt).inSeconds;
    if (gap < 3) return; // do not talk non-stop
    if (text == _lastSpoken && gap < 6) return; // do not repeat too fast
    _lastSpoken = text;
    _lastSpokenAt = DateTime.now();
    _tts.speak(text);
  }

  // ---------- camera ----------
  Future<void> _initCameras() async {
    try {
      _cams = await availableCameras();
      if (_cams.isEmpty) {
        if (mounted) setState(() => _error = 'No camera found on this device');
        return;
      }
      // Prefer the FRONT camera so the dancer can see themselves.
      final front =
          _cams.indexWhere((c) => c.lensDirection == CameraLensDirection.front);
      await _openCamera(front >= 0 ? front : 0);
    } catch (e) {
      if (mounted) {
        setState(() => _error = 'Camera problem: allow camera permission');
      }
    }
  }

  Future<void> _openCamera(int index) async {
    final old = _controller;
    if (old != null) {
      setState(() => _controller = null);
      await WidgetsBinding.instance.endOfFrame; // let the preview go first
      await old.dispose();
    }
    final controller = CameraController(
      _cams[index],
      ResolutionPreset.medium, // small pictures = faster
      enableAudio: false,
    );
    try {
      await controller.initialize();
    } catch (e) {
      if (mounted) {
        setState(() => _error = 'Camera problem: allow camera permission');
      }
      return;
    }
    if (!mounted) {
      await controller.dispose();
      return;
    }
    setState(() {
      _controller = controller;
      _camIndex = index;
      _error = null;
    });
  }

  void _switchCamera() {
    if (_running || _cams.length < 2) return;
    _openCamera((_camIndex + 1) % _cams.length);
  }

  // ---------- AI loop ----------
  Future<void> _start() async {
    try {
      await _api.reset(); // new session = fresh report
    } catch (_) {
      setState(() =>
          _error = 'Cannot reach AI server. Same Wi-Fi? Server running?');
      return;
    }
    setState(() {
      _running = true;
      _error = null;
      _result = null;
    });
    _loop();
  }

  // Take photo -> send to AI -> show answer -> repeat (waits for each answer,
  // so requests never pile up).
  Future<void> _loop() async {
    while (_running && mounted) {
      final sw = Stopwatch()..start();
      try {
        final file = await _controller!.takePicture();
        final bytes = await file.readAsBytes();
        final r = await _api.analyze(bytes);
        if (!mounted || !_running) break;
        setState(() {
          _result = r;
          _error = null;
        });
        _maybeSpeak(_tipsFor(r));
      } catch (e) {
        if (!mounted) break;
        setState(() =>
            _error = 'Cannot reach AI server. Same Wi-Fi? Server running?');
        await Future.delayed(const Duration(seconds: 1));
      }
      final wait = 300 - sw.elapsedMilliseconds; // aim for ~3 photos/second
      if (wait > 0) await Future.delayed(Duration(milliseconds: wait));
    }
  }

  Future<void> _stop() async {
    setState(() => _running = false);
    _tts.stop();
    try {
      final report = await _api.report();
      if (!mounted) return;
      Navigator.push(
        context,
        MaterialPageRoute(
            builder: (_) => GarbaAiReportScreen(report: report)),
      );
    } catch (_) {
      if (mounted) setState(() => _error = 'Could not get report from server');
    }
  }

  // ---------- server address dialog ----------
  Future<void> _editServer() async {
    final ctrl = TextEditingController(text: _api.baseUrl);
    final newUrl = await showDialog<String>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('AI server address'),
        content: TextField(
          controller: ctrl,
          autofocus: true,
          keyboardType: TextInputType.url,
          decoration: const InputDecoration(hintText: 'http://192.168.1.5:8000'),
        ),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(ctx),
              child: const Text('Cancel')),
          FilledButton(
              onPressed: () => Navigator.pop(ctx, ctrl.text),
              child: const Text('Save & test')),
        ],
      ),
    );
    if (newUrl == null || newUrl.trim().isEmpty || !mounted) return;

    final api = GarbaAiApi(newUrl);
    GarbaAiConfig.serverUrl = api.baseUrl;
    setState(() => _api = api);

    String msg;
    try {
      final steps = await api.health();
      msg = 'Connected. ${steps.length} garba steps saved on server.';
    } catch (_) {
      msg = 'Cannot reach that address. Same Wi-Fi? Server running?';
    }
    if (!mounted) return;
    ScaffoldMessenger.of(context)
        .showSnackBar(SnackBar(content: Text(msg)));
  }

  @override
  void dispose() {
    _running = false;
    _tts.stop();
    _controller?.dispose();
    super.dispose();
  }

  Color _scoreColor(double s) =>
      s >= 70 ? Colors.green : (s >= 50 ? Colors.orange : Colors.red);

  // ---------- screen ----------
  @override
  Widget build(BuildContext context) {
    final c = _controller;
    final r = _result;

    return Scaffold(
      appBar: AppBar(
        title: const Text('AI Garba Trainer'),
        actions: [
          PopupMenuButton<String>(
            tooltip: 'Language',
            icon: const Icon(Icons.translate),
            initialValue: _lang,
            onSelected: _setLang,
            itemBuilder: (_) => [
              for (final e in _langNames.entries)
                PopupMenuItem(value: e.key, child: Text(e.value)),
            ],
          ),
          IconButton(
            tooltip: _voiceOn ? 'Voice on' : 'Voice off',
            icon: Icon(_voiceOn ? Icons.volume_up : Icons.volume_off),
            onPressed: () {
              setState(() => _voiceOn = !_voiceOn);
              if (!_voiceOn) _tts.stop();
            },
          ),
          IconButton(
            tooltip: 'Switch camera',
            icon: const Icon(Icons.cameraswitch),
            onPressed: _running ? null : _switchCamera,
          ),
          IconButton(
            tooltip: 'AI server address',
            icon: const Icon(Icons.settings_ethernet),
            onPressed: _running ? null : _editServer,
          ),
        ],
      ),
      body: c == null || !c.value.isInitialized
          ? Center(child: Text(_error ?? 'Starting camera...'))
          : Stack(
              fit: StackFit.expand,
              children: [
                CameraPreview(c),

                // Score + step name (top)
                if (r != null && r.found && r.step != null)
                  Positioned(
                    top: 12,
                    left: 12,
                    right: 12,
                    child: Card(
                      color: Colors.black54,
                      child: Padding(
                        padding: const EdgeInsets.all(12),
                        child: Row(
                          children: [
                            Text(
                              r.score.toStringAsFixed(0),
                              style: TextStyle(
                                fontSize: 48,
                                fontWeight: FontWeight.bold,
                                color: _scoreColor(r.score),
                              ),
                            ),
                            const SizedBox(width: 16),
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text('Step: ${r.step}',
                                      style: const TextStyle(
                                          color: Colors.white, fontSize: 18)),
                                  Text(r.grade,
                                      style: TextStyle(
                                          color: _scoreColor(r.score),
                                          fontSize: 16)),
                                ],
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                  ),

                // "Body not found" message
                if (r != null && !r.found)
                  Positioned(
                    top: 12,
                    left: 12,
                    right: 12,
                    child: Card(
                      color: Colors.red.shade700,
                      child: Padding(
                        padding: const EdgeInsets.all(12),
                        child: Text(r.message,
                            style: const TextStyle(color: Colors.white)),
                      ),
                    ),
                  ),

                // Errors + live correction tips
                Positioned(
                  bottom: 100,
                  left: 12,
                  right: 12,
                  child: Column(
                    children: [
                      if (_error != null)
                        Card(
                          color: Colors.red.shade700,
                          child: Padding(
                            padding: const EdgeInsets.all(10),
                            child: Text(_error!,
                                style: const TextStyle(color: Colors.white)),
                          ),
                        ),
                      for (final tip in _tipsFor(r))
                        Card(
                          color: Colors.deepOrange,
                          child: Padding(
                            padding: const EdgeInsets.all(10),
                            child: Text(tip,
                                style: const TextStyle(
                                    color: Colors.white,
                                    fontSize: 20,
                                    fontWeight: FontWeight.w600)),
                          ),
                        ),
                    ],
                  ),
                ),

                // Start / Stop button
                Positioned(
                  bottom: 24,
                  left: 24,
                  right: 24,
                  child: SizedBox(
                    height: 56,
                    child: FilledButton.icon(
                      onPressed: _running ? _stop : _start,
                      icon: Icon(_running ? Icons.stop : Icons.play_arrow),
                      label: Text(
                          _running ? 'Finish & see report' : 'Start dancing'),
                    ),
                  ),
                ),
              ],
            ),
    );
  }
}
