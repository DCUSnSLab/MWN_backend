// Android FCM 메시지 수신 서비스
// app/src/main/java/[your_package]/fcm/MyFirebaseMessagingService.java

package com.yourcompany.weatherapp.fcm;

import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.media.RingtoneManager;
import android.net.Uri;
import android.os.Build;
import android.util.Log;

import androidx.core.app.NotificationCompat;

import com.google.firebase.messaging.FirebaseMessagingService;
import com.google.firebase.messaging.RemoteMessage;

import com.yourcompany.weatherapp.MainActivity;
import com.yourcompany.weatherapp.R;

public class MyFirebaseMessagingService extends FirebaseMessagingService {
    
    private static final String TAG = "MyFirebaseMsgService";
    private static final String CHANNEL_ID = "weather_alerts";
    private static final String SEVERE_CHANNEL_ID = "severe_weather";

    @Override
    public void onMessageReceived(RemoteMessage remoteMessage) {
        // 메시지 수신 로그
        Log.d(TAG, "From: " + remoteMessage.getFrom());

        // 데이터 페이로드 확인
        if (remoteMessage.getData().size() > 0) {
            Log.d(TAG, "Message data payload: " + remoteMessage.getData());
            handleDataMessage(remoteMessage);
        }

        // 알림 페이로드 확인
        if (remoteMessage.getNotification() != null) {
            Log.d(TAG, "Message Notification Body: " + remoteMessage.getNotification().getBody());
            handleNotificationMessage(remoteMessage);
        }
    }

    @Override
    public void onNewToken(String token) {
        Log.d(TAG, "Refreshed token: " + token);
        
        // 새 토큰을 서버에 전송
        sendRegistrationToServer(token);
    }

    private void handleDataMessage(RemoteMessage remoteMessage) {
        String type = remoteMessage.getData().get("type");
        String weatherData = remoteMessage.getData().get("weather_data");
        
        // 데이터 메시지 처리
        if ("severe_weather".equals(type)) {
            // 심각한 날씨 알림 처리
            sendSevereWeatherNotification(remoteMessage);
        } else {
            // 일반 날씨 알림 처리
            sendNotification(remoteMessage);
        }
    }

    private void handleNotificationMessage(RemoteMessage remoteMessage) {
        String title = remoteMessage.getNotification().getTitle();
        String body = remoteMessage.getNotification().getBody();
        String type = remoteMessage.getData().get("type");
        
        if ("severe_weather".equals(type)) {
            sendSevereWeatherNotification(remoteMessage);
        } else {
            sendNotification(remoteMessage);
        }
    }

    private void sendNotification(RemoteMessage remoteMessage) {
        Intent intent = new Intent(this, MainActivity.class);
        intent.addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP);
        
        // 날씨 데이터를 인텐트에 추가
        String weatherData = remoteMessage.getData().get("weather_data");
        if (weatherData != null) {
            intent.putExtra("weather_data", weatherData);
        }
        
        PendingIntent pendingIntent = PendingIntent.getActivity(this, 0, intent,
                PendingIntent.FLAG_ONE_SHOT | PendingIntent.FLAG_IMMUTABLE);

        String channelId = CHANNEL_ID;
        Uri defaultSoundUri = RingtoneManager.getDefaultUri(RingtoneManager.TYPE_NOTIFICATION);
        
        String title = remoteMessage.getNotification() != null ? 
                      remoteMessage.getNotification().getTitle() : "날씨 알림";
        String body = remoteMessage.getNotification() != null ? 
                     remoteMessage.getNotification().getBody() : "새로운 날씨 정보가 있습니다.";

        NotificationCompat.Builder notificationBuilder =
                new NotificationCompat.Builder(this, channelId)
                        .setSmallIcon(R.drawable.ic_notification)
                        .setContentTitle(title)
                        .setContentText(body)
                        .setAutoCancel(true)
                        .setSound(defaultSoundUri)
                        .setContentIntent(pendingIntent)
                        .setPriority(NotificationCompat.PRIORITY_DEFAULT);

        NotificationManager notificationManager =
                (NotificationManager) getSystemService(Context.NOTIFICATION_SERVICE);

        // 알림 채널 생성 (Android 8.0+)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            NotificationChannel channel = new NotificationChannel(channelId,
                    "날씨 알림",
                    NotificationManager.IMPORTANCE_DEFAULT);
            channel.setDescription("일반 날씨 알림");
            notificationManager.createNotificationChannel(channel);
        }

        notificationManager.notify(0, notificationBuilder.build());
    }

    private void sendSevereWeatherNotification(RemoteMessage remoteMessage) {
        Intent intent = new Intent(this, MainActivity.class);
        intent.addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP);
        intent.putExtra("severe_weather", true);
        
        String weatherData = remoteMessage.getData().get("weather_data");
        if (weatherData != null) {
            intent.putExtra("weather_data", weatherData);
        }
        
        PendingIntent pendingIntent = PendingIntent.getActivity(this, 1, intent,
                PendingIntent.FLAG_ONE_SHOT | PendingIntent.FLAG_IMMUTABLE);

        String channelId = SEVERE_CHANNEL_ID;
        Uri alertSoundUri = RingtoneManager.getDefaultUri(RingtoneManager.TYPE_ALARM);
        
        String title = remoteMessage.getNotification() != null ? 
                      remoteMessage.getNotification().getTitle() : "⚠️ 기상 특보";
        String body = remoteMessage.getNotification() != null ? 
                     remoteMessage.getNotification().getBody() : "심각한 날씨 상황이 발생했습니다.";

        NotificationCompat.Builder notificationBuilder =
                new NotificationCompat.Builder(this, channelId)
                        .setSmallIcon(R.drawable.ic_warning)
                        .setContentTitle(title)
                        .setContentText(body)
                        .setAutoCancel(true)
                        .setSound(alertSoundUri)
                        .setContentIntent(pendingIntent)
                        .setPriority(NotificationCompat.PRIORITY_HIGH)
                        .setCategory(NotificationCompat.CATEGORY_ALARM)
                        .setOngoing(true)  // 사용자가 직접 닫아야 함
                        .addAction(R.drawable.ic_action_view, "자세히 보기", pendingIntent);

        NotificationManager notificationManager =
                (NotificationManager) getSystemService(Context.NOTIFICATION_SERVICE);

        // 심각한 날씨 알림 채널 생성 (Android 8.0+)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            NotificationChannel channel = new NotificationChannel(channelId,
                    "기상 특보",
                    NotificationManager.IMPORTANCE_HIGH);
            channel.setDescription("심각한 날씨 상황 알림");
            channel.enableLights(true);
            channel.enableVibration(true);
            channel.setVibrationPattern(new long[]{1000, 1000, 1000, 1000, 1000});
            notificationManager.createNotificationChannel(channel);
        }

        notificationManager.notify(1, notificationBuilder.build());
    }

    private void sendRegistrationToServer(String token) {
        // 서버에 토큰 전송 로직
        // 실제 앱에서는 Retrofit, OkHttp 등을 사용하여 API 호출
        Log.d(TAG, "Sending token to server: " + token);
        
        // 예시: SharedPreferences에 토큰 저장
        getSharedPreferences("FCM", MODE_PRIVATE)
                .edit()
                .putString("token", token)
                .apply();
                
        // TODO: 실제 서버 API 호출
        // APIService.registerFCMToken(token, userAuthToken);
    }
}