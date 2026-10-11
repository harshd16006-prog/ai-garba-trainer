// lib/main.dart
// ONLY for testing the AI module on its own.
// When you merge into the real Garba app, DO NOT copy this file.
import 'package:flutter/material.dart';
import 'garba_ai/garba_ai.dart';

void main() {
  runApp(MaterialApp(
    title: 'AI Garba Trainer (test)',
    debugShowCheckedModeBanner: false,
    theme: ThemeData(colorSchemeSeed: Colors.deepOrange, useMaterial3: true),
    home: const GarbaAiTrainerScreen(),
  ));
}
