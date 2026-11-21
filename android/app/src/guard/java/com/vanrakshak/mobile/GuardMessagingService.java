package com.vanrakshak.mobile;
import android.app.*;
import android.content.Intent;
import com.google.firebase.messaging.*;
public class GuardMessagingService extends FirebaseMessagingService {
 @Override public void onNewToken(String token){PushSupport.tokenRefreshed();}
 @Override public void onMessageReceived(RemoteMessage message){
  NotificationManager manager=getSystemService(NotificationManager.class);
  if(!manager.areNotificationsEnabled())return;
  manager.createNotificationChannel(new NotificationChannel("incident_alerts","Team incident alerts",NotificationManager.IMPORTANCE_HIGH));
  Intent intent=new Intent(this,MainActivity.class).addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP);
  intent.putExtra("incidentType",message.getData().get("incidentType"));intent.putExtra("incidentId",message.getData().get("incidentId"));
  int id=(message.getData().getOrDefault("incidentType","")+":"+message.getData().getOrDefault("incidentId","")).hashCode();
  PendingIntent open=PendingIntent.getActivity(this,id,intent,PendingIntent.FLAG_UPDATE_CURRENT|PendingIntent.FLAG_IMMUTABLE);
  manager.notify(id,new Notification.Builder(this,"incident_alerts").setSmallIcon(com.vanrakshak.mobile.R.drawable.ic_alert).setContentTitle("VanRakshak: new assignment").setContentText("Open the guard app to review your team’s incident.").setAutoCancel(true).setContentIntent(open).build());
 }
}
