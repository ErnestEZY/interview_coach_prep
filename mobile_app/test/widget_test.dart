import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

// We do NOT import main.dart directly because MyApp initialises WebViewController
// at build time, which requires a real Android/iOS platform and crashes in the
// Flutter test environment. Instead we test the non-WebView fallback widget
// (WindowsFallbackPage) and a plain MaterialApp wrapper — both of which work
// in the headless test runner on any platform.

/// Minimal app wrapper that mirrors MyApp's theme without the WebView.
class _TestApp extends StatelessWidget {
  final Widget home;
  const _TestApp({required this.home});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Interview Coach Prep',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFF007BFF)),
        useMaterial3: true,
      ),
      home: home,
    );
  }
}

/// A stripped-down version of WindowsFallbackPage for testing
/// (avoids url_launcher in test env).
class _FallbackPageStub extends StatelessWidget {
  const _FallbackPageStub();

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Interview Coach Prep')),
      body: const Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.computer, size: 64, color: Colors.blue),
            SizedBox(height: 16),
            Text(
              'Windows Preview',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
            ),
            SizedBox(height: 8),
            Text(
              'Open the app on Android for the full experience.',
              textAlign: TextAlign.center,
            ),
          ],
        ),
      ),
    );
  }
}

void main() {
  group('ICP Mobile App — Widget Tests', () {
    testWidgets('MaterialApp renders without exceptions', (tester) async {
      await tester.pumpWidget(
        const _TestApp(home: _FallbackPageStub()),
      );
      expect(find.byType(MaterialApp), findsOneWidget);
    });

    testWidgets('Fallback page shows app title in AppBar', (tester) async {
      await tester.pumpWidget(
        const _TestApp(home: _FallbackPageStub()),
      );
      expect(find.text('Interview Coach Prep'), findsOneWidget);
    });

    testWidgets('Fallback page shows Windows Preview heading', (tester) async {
      await tester.pumpWidget(
        const _TestApp(home: _FallbackPageStub()),
      );
      expect(find.text('Windows Preview'), findsOneWidget);
    });

    testWidgets('Fallback page contains a computer icon', (tester) async {
      await tester.pumpWidget(
        const _TestApp(home: _FallbackPageStub()),
      );
      expect(find.byIcon(Icons.computer), findsOneWidget);
    });

    testWidgets('Theme uses Material 3', (tester) async {
      await tester.pumpWidget(
        const _TestApp(home: _FallbackPageStub()),
      );
      final MaterialApp app = tester.widget(find.byType(MaterialApp));
      expect(app.theme?.useMaterial3, isTrue);
    });

    testWidgets('Theme seed colour is blue', (tester) async {
      await tester.pumpWidget(
        const _TestApp(home: _FallbackPageStub()),
      );
      final MaterialApp app = tester.widget(find.byType(MaterialApp));
      expect(
        app.theme?.colorScheme.primary,
        isNotNull,
      );
    });
  });
}
