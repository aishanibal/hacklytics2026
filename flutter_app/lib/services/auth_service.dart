import '../models/app_user.dart';

class AuthService {
  final Map<String, _StoredUser> _users = {};

  AppUser? signUp({
    required String name,
    required String email,
    required String password,
    required UserRole role,
  }) {
    if (_users.containsKey(email)) return null;
    final user = AppUser(
      id: DateTime.now().millisecondsSinceEpoch.toString(),
      name: name,
      email: email,
      role: role,
      createdAt: DateTime.now(),
    );
    _users[email] = _StoredUser(user: user, password: password);
    return user;
  }

  AppUser? login({
    required String email,
    required String password,
  }) {
    final stored = _users[email];
    if (stored == null || stored.password != password) return null;
    return stored.user;
  }
}

class _StoredUser {
  final AppUser user;
  final String password;
  const _StoredUser({required this.user, required this.password});
}
