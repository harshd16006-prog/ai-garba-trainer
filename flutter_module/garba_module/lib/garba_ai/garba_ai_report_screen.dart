// lib/garba_ai/garba_ai_report_screen.dart
// Shows the performance report that the Python AI calculated.
import 'package:flutter/material.dart';

class GarbaAiReportScreen extends StatelessWidget {
  const GarbaAiReportScreen({super.key, required this.report});

  final Map<String, dynamic> report;

  String _friendly(String joint) => joint.replaceAll('_', ' ');

  @override
  Widget build(BuildContext context) {
    final frames = (report['frames'] ?? 0) as num;

    if (frames == 0) {
      return Scaffold(
        appBar: AppBar(title: const Text('Performance Report')),
        body: const Center(
          child: Padding(
            padding: EdgeInsets.all(24),
            child: Text(
              'No dance was detected. Stand 2-3 metres back so your '
              'whole body is visible, then try again.',
              textAlign: TextAlign.center,
            ),
          ),
        ),
      );
    }

    final avg = ((report['average_score'] ?? 0) as num).toDouble();
    final best = ((report['best_score'] ?? 0) as num).toDouble();
    final worst = ((report['worst_score'] ?? 0) as num).toDouble();
    final grade = (report['grade'] ?? '') as String;
    final steps = Map<String, dynamic>.from(report['steps_practiced'] ?? {});
    final weak = List<String>.from(report['weakest_joints'] ?? const []);

    return Scaffold(
      appBar: AppBar(title: const Text('Performance Report')),
      body: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          Center(
            child: Text(
              avg.toStringAsFixed(0),
              style:
                  const TextStyle(fontSize: 90, fontWeight: FontWeight.bold),
            ),
          ),
          Center(
            child: Text(grade,
                style: Theme.of(context).textTheme.headlineSmall),
          ),
          const SizedBox(height: 24),
          Row(
            children: [
              _stat('Best', best.toStringAsFixed(0)),
              _stat('Worst', worst.toStringAsFixed(0)),
              _stat('Checks', frames.toString()),
            ],
          ),
          const SizedBox(height: 24),
          Text('Steps practiced',
              style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 8),
          for (final e in steps.entries)
            ListTile(
              dense: true,
              leading: const Icon(Icons.music_note),
              title: Text(e.key),
              trailing: Text('${e.value}x'),
            ),
          const SizedBox(height: 16),
          Text('Work on these',
              style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 8),
          if (weak.isEmpty)
            const Text('Nothing - great form!')
          else
            for (final j in weak)
              ListTile(
                dense: true,
                leading:
                    const Icon(Icons.warning_amber, color: Colors.orange),
                title: Text(_friendly(j)),
              ),
          const SizedBox(height: 24),
          FilledButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Practice again'),
          ),
        ],
      ),
    );
  }

  Widget _stat(String label, String value) => Expanded(
        child: Column(
          children: [
            Text(value,
                style: const TextStyle(
                    fontSize: 28, fontWeight: FontWeight.bold)),
            Text(label),
          ],
        ),
      );
}
