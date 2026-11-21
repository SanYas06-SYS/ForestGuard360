package com.vanrakshak.mobile;
import android.Manifest;
import android.os.Build;
import android.app.*;
import android.content.pm.PackageManager;
import com.google.firebase.FirebaseApp;
import com.google.firebase.messaging.FirebaseMessaging;
final class PushSupport {
 private static java.lang.ref.WeakReference<MainActivity> current = new java.lang.ref.WeakReference<>(null);
 static void tokenRefreshed(){MainActivity a=current.get();if(a!=null&&!a.isFinishing()&&!a.isDestroyed())a.runOnUiThread(()->attach(a));}
 static void setup(MainActivity a){
  a.getSystemService(NotificationManager.class).createNotificationChannel(new NotificationChannel("incident_alerts","Team incident alerts",NotificationManager.IMPORTANCE_HIGH));
  if(Build.VERSION.SDK_INT>=33&&a.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS)!=PackageManager.PERMISSION_GRANTED)
   new AlertDialog.Builder(a).setTitle("Team assignment alerts").setMessage("Allow notifications to see new team assignments when this app is closed.").setNegativeButton("Later",null).setPositiveButton("Continue",(d,w)->a.requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS},12)).show();
 }
 static void attach(MainActivity a){
  current=new java.lang.ref.WeakReference<>(a);
  if(FirebaseApp.getApps(a).isEmpty()){a.pushState("","Firebase configuration is pending. Use the assignment inbox.");return;}
  if(!a.getSystemService(NotificationManager.class).areNotificationsEnabled()){a.pushState("","Notifications are disabled in Android settings.");return;}
  FirebaseMessaging.getInstance().getToken().addOnSuccessListener(token->a.pushState(token,"Android notification token ready.")).addOnFailureListener(error->a.pushState("","Could not connect to Firebase. Reopen the app to retry."));
 }
}
