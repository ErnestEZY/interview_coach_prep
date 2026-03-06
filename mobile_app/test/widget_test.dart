import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:interview_coach_app/main.dart';

void main() {
  testWidgets('App builds without exceptions', (WidgetTester tester) async {
    await tester.pumpWidget(const MyApp());
    expect(find.byType(MaterialApp), findsOneWidget);
  });
}
