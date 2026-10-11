// lib/garba_ai/garba_ai_api.dart
// The "phone call" between the app and the Python AI server.
import 'dart:convert';
import 'package:http/http.dart' as http;

class GarbaAiResult {
  final bool found; // is a body visible?
  final String? step; // which garba pose was recognised
  final double score; // 0 - 100
  final String grade; // Excellent / Good / ...
  final List<String> tips; // live corrections
  final String message; // problems like "stand in view"

  GarbaAiResult({
    required this.found,
    required this.step,
    required this.score,
    required this.grade,
    required this.tips,
    required this.message,
  });

  factory GarbaAiResult.fromJson(Map<String, dynamic> j) => GarbaAiResult(
        found: j['found'] == true,
        step: j['step'] as String?,
        score: ((j['score'] ?? 0) as num).toDouble(),
        grade: (j['grade'] ?? '') as String,
        tips: List<String>.from(j['tips'] ?? const []),
        message: (j['message'] ?? '') as String,
      );
}

class GarbaAiApi {
  GarbaAiApi(String url) : baseUrl = _clean(url);

  final String baseUrl;

  // "192.168.1.5:8000" -> "http://192.168.1.5:8000"
  static String _clean(String url) {
    var s = url.trim();
    if (!s.startsWith('http://') && !s.startsWith('https://')) {
      s = 'http://$s';
    }
    while (s.endsWith('/')) {
      s = s.substring(0, s.length - 1);
    }
    return s;
  }

  /// Send one camera picture (JPEG bytes), get score + tips back.
  Future<GarbaAiResult> analyze(List<int> jpegBytes) async {
    final res = await http
        .post(
          Uri.parse('$baseUrl/analyze'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({'image': base64Encode(jpegBytes)}),
        )
        .timeout(const Duration(seconds: 6));
    if (res.statusCode != 200) {
      throw Exception('Server error ${res.statusCode}');
    }
    return GarbaAiResult.fromJson(
        jsonDecode(res.body) as Map<String, dynamic>);
  }

  /// Whole-session performance report.
  Future<Map<String, dynamic>> report() async {
    final res = await http
        .get(Uri.parse('$baseUrl/report'))
        .timeout(const Duration(seconds: 6));
    return jsonDecode(res.body) as Map<String, dynamic>;
  }

  /// Start a fresh session (clears the old report).
  Future<void> reset() async {
    await http
        .post(Uri.parse('$baseUrl/reset'))
        .timeout(const Duration(seconds: 6));
  }

  /// Is the server alive? Returns the list of saved garba steps.
  Future<List<String>> health() async {
    final res = await http
        .get(Uri.parse('$baseUrl/health'))
        .timeout(const Duration(seconds: 4));
    final j = jsonDecode(res.body) as Map<String, dynamic>;
    return List<String>.from(j['steps'] ?? const []);
  }
}
