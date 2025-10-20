// iOS FCM 헬퍼 클래스
// FCMHelper.swift

import Foundation
import Firebase
import FirebaseMessaging
import UserNotifications

class FCMHelper: NSObject {
    static let shared = FCMHelper()
    
    private override init() {
        super.init()
    }
    
    // Firebase 초기화
    func configure() {
        FirebaseApp.configure()
        
        // FCM 델리게이트 설정
        Messaging.messaging().delegate = self
        
        // 알림 권한 요청
        requestNotificationPermission()
        
        // 현재 FCM 토큰 가져오기
        getCurrentToken()
    }
    
    // 알림 권한 요청
    private func requestNotificationPermission() {
        UNUserNotificationCenter.current().delegate = self
        
        let authOptions: UNAuthorizationOptions = [.alert, .badge, .sound]
        UNUserNotificationCenter.current().requestAuthorization(
            options: authOptions,
            completionHandler: { granted, error in
                if let error = error {
                    print("Notification permission error: \(error)")
                } else if granted {
                    print("Notification permission granted")
                    DispatchQueue.main.async {
                        UIApplication.shared.registerForRemoteNotifications()
                    }
                } else {
                    print("Notification permission denied")
                }
            }
        )
    }
    
    // 현재 FCM 토큰 가져오기
    func getCurrentToken() {
        Messaging.messaging().token { token, error in
            if let error = error {
                print("Error fetching FCM registration token: \(error)")
            } else if let token = token {
                print("FCM registration token: \(token)")
                self.sendTokenToServer(token)
            }
        }
    }
    
    // 서버에 토큰 전송
    private func sendTokenToServer(_ token: String) {
        guard let url = URL(string: "YOUR_SERVER_URL/api/fcm/register") else { return }
        guard let userToken = getUserAuthToken() else { return }
        
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("Bearer \(userToken)", forHTTPHeaderField: "Authorization")
        
        let deviceInfo: [String: Any] = [
            "platform": "ios",
            "device_model": UIDevice.current.model,
            "system_version": UIDevice.current.systemVersion,
            "app_version": Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "Unknown",
            "timestamp": ISO8601DateFormatter().string(from: Date())
        ]
        
        let body: [String: Any] = [
            "token": token,
            "device_info": deviceInfo,
            "subscribe_topics": ["weather_alerts", "severe_weather"]
        ]
        
        do {
            request.httpBody = try JSONSerialization.data(withJSONObject: body)
        } catch {
            print("Error serializing JSON: \(error)")
            return
        }
        
        URLSession.shared.dataTask(with: request) { data, response, error in
            if let error = error {
                print("Error sending token to server: \(error)")
                return
            }
            
            if let httpResponse = response as? HTTPURLResponse {
                if httpResponse.statusCode == 200 {
                    print("Token registered successfully")
                } else {
                    print("Failed to register token: \(httpResponse.statusCode)")
                }
            }
        }.resume()
    }
    
    // 사용자 인증 토큰 가져오기 (KeyChain 등에서)
    private func getUserAuthToken() -> String? {
        // TODO: 실제 앱에서는 KeyChain이나 UserDefaults에서 가져오기
        return UserDefaults.standard.string(forKey: "user_auth_token")
    }
    
    // 로컬 알림 표시
    func showLocalNotification(title: String, body: String, userInfo: [AnyHashable: Any] = [:]) {
        let content = UNMutableNotificationContent()
        content.title = title
        content.body = body
        content.sound = UNNotificationSound.default
        content.userInfo = userInfo
        
        // 심각한 날씨인 경우 특별 처리
        if let type = userInfo["type"] as? String, type == "severe_weather" {
            content.sound = UNNotificationSound(named: UNNotificationSoundName("alert.wav"))
            content.categoryIdentifier = "SEVERE_WEATHER_CATEGORY"
        } else {
            content.categoryIdentifier = "WEATHER_CATEGORY"
        }
        
        let request = UNNotificationRequest(
            identifier: UUID().uuidString,
            content: content,
            trigger: nil
        )
        
        UNUserNotificationCenter.current().add(request) { error in
            if let error = error {
                print("Error showing local notification: \(error)")
            }
        }
    }
    
    // 알림 카테고리 설정
    func setupNotificationCategories() {
        // 일반 날씨 알림 액션
        let viewAction = UNNotificationAction(
            identifier: "VIEW_ACTION",
            title: "자세히 보기",
            options: [.foreground]
        )
        
        let dismissAction = UNNotificationAction(
            identifier: "DISMISS_ACTION",
            title: "닫기",
            options: []
        )
        
        // 일반 날씨 카테고리
        let weatherCategory = UNNotificationCategory(
            identifier: "WEATHER_CATEGORY",
            actions: [viewAction, dismissAction],
            intentIdentifiers: [],
            options: []
        )
        
        // 심각한 날씨 카테고리
        let severeWeatherCategory = UNNotificationCategory(
            identifier: "SEVERE_WEATHER_CATEGORY",
            actions: [viewAction],
            intentIdentifiers: [],
            options: [.customDismissAction]
        )
        
        UNUserNotificationCenter.current().setNotificationCategories([
            weatherCategory,
            severeWeatherCategory
        ])
    }
}

// MARK: - MessagingDelegate
extension FCMHelper: MessagingDelegate {
    func messaging(_ messaging: Messaging, didReceiveRegistrationToken fcmToken: String?) {
        print("Firebase registration token: \(String(describing: fcmToken))")
        
        if let token = fcmToken {
            sendTokenToServer(token)
        }
    }
}

// MARK: - UNUserNotificationCenterDelegate
extension FCMHelper: UNUserNotificationCenterDelegate {
    // 포그라운드에서 알림 수신
    func userNotificationCenter(_ center: UNUserNotificationCenter,
                              willPresent notification: UNNotification,
                              withCompletionHandler completionHandler: @escaping (UNNotificationPresentationOptions) -> Void) {
        let userInfo = notification.request.content.userInfo
        
        print("Will present notification with userInfo: \(userInfo)")
        
        // 알림 표시 옵션
        completionHandler([[.alert, .sound, .badge]])
    }
    
    // 알림 탭 처리
    func userNotificationCenter(_ center: UNUserNotificationCenter,
                              didReceive response: UNNotificationResponse,
                              withCompletionHandler completionHandler: @escaping () -> Void) {
        let userInfo = response.notification.request.content.userInfo
        let actionIdentifier = response.actionIdentifier
        
        print("Did receive notification response: \(actionIdentifier)")
        print("UserInfo: \(userInfo)")
        
        switch actionIdentifier {
        case "VIEW_ACTION":
            // 날씨 화면으로 이동
            navigateToWeatherScreen(userInfo: userInfo)
        case "DISMISS_ACTION":
            // 알림 닫기 (기본 동작)
            break
        case UNNotificationDefaultActionIdentifier:
            // 알림 자체를 탭한 경우
            navigateToWeatherScreen(userInfo: userInfo)
        default:
            break
        }
        
        completionHandler()
    }
    
    private func navigateToWeatherScreen(userInfo: [AnyHashable: Any]) {
        // 메인 스레드에서 화면 이동 처리
        DispatchQueue.main.async {
            // TODO: 실제 앱에서는 적절한 뷰 컨트롤러로 이동
            if let weatherData = userInfo["weather_data"] as? String {
                print("Navigate to weather screen with data: \(weatherData)")
                // NotificationCenter.default.post(name: .showWeatherDetail, object: weatherData)
            }
        }
    }
}

// MARK: - Notification Names
extension Notification.Name {
    static let showWeatherDetail = Notification.Name("showWeatherDetail")
}