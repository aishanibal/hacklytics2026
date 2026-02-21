import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/app_user.dart';
import '../services/auth_service.dart';

final authServiceProvider = Provider((_) => AuthService());

final authProvider = StateNotifierProvider<AuthNotifier, AppUser?>((ref) {
  return AuthNotifier(ref.read(authServiceProvider));
});

class AuthNotifier extends StateNotifier<AppUser?> {
  AuthNotifier(this._authService) : super(null);
  final AuthService _authService;

  String? signUp({
    required String name,
    required String email,
    required String password,
    required UserRole role,
  }) {
    final user = _authService.signUp(
      name: name,
      email: email,
      password: password,
      role: role,
    );
    if (user == null) return 'Email already in use';
    state = user;
    return null;
  }

  String? login({required String email, required String password}) {
    final user = _authService.login(email: email, password: password);
    if (user == null) return 'Invalid email or password';
    state = user;
    return null;
  }

  void logout() => state = null;
}
