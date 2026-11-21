package com.vanrakshak.mobile;
import android.Manifest;
import android.app.*;
import android.os.*;
import android.content.*;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.graphics.Color;
import android.webkit.*;
import android.view.*;
import android.widget.*;
import org.json.JSONObject;

public class MainActivity extends androidx.activity.ComponentActivity {
    private WebView web;
    private TextView status;
    private ValueCallback<Uri[]> files;
    private GeolocationPermissions.Callback locationCallback;
    private String locationOrigin;
    static boolean trusted(String url) {
        if (url == null) return false;
        Uri u=Uri.parse(url), base=Uri.parse(BuildConfig.BASE_URL);
        return "https".equals(u.getScheme()) && base.getHost().equals(u.getHost()) && (u.getPort()==-1||u.getPort()==443);
    }
    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        getOnBackPressedDispatcher().addCallback(this,new androidx.activity.OnBackPressedCallback(true){
            @Override public void handleOnBackPressed(){if(web!=null&&web.canGoBack())web.goBack();else finish();}
        });
        LinearLayout root=new LinearLayout(this);root.setOrientation(LinearLayout.VERTICAL);root.setBackgroundColor(Color.rgb(244,247,241));
        root.setOnApplyWindowInsetsListener((v,insets)->{if(Build.VERSION.SDK_INT>=30){android.graphics.Insets bars=insets.getInsets(WindowInsets.Type.systemBars());v.setPadding(bars.left,bars.top,bars.right,bars.bottom);}else{v.setPadding(insets.getSystemWindowInsetLeft(),insets.getSystemWindowInsetTop(),insets.getSystemWindowInsetRight(),insets.getSystemWindowInsetBottom());}return insets;});
        LinearLayout bar=new LinearLayout(this);bar.setPadding(8,4,8,4);
        Button home=new Button(this);home.setText(BuildConfig.IS_GUARD?"Guard home":"Community home");home.setOnClickListener(v->web.loadUrl(BuildConfig.BASE_URL+homePath()));bar.addView(home,new LinearLayout.LayoutParams(0,48,1));
        Button reload=new Button(this);reload.setText("Retry");reload.setOnClickListener(v->web.reload());bar.addView(reload);root.addView(bar);
        status=new TextView(this);status.setPadding(16,8,16,8);root.addView(status);
        web=new WebView(this);root.addView(web,new LinearLayout.LayoutParams(-1,0,1));setContentView(root);
        WebSettings settings=web.getSettings();settings.setJavaScriptEnabled(true);settings.setDomStorageEnabled(true);settings.setGeolocationEnabled(true);
        settings.setAllowFileAccess(false);settings.setAllowContentAccess(true);settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        settings.setUserAgentString(settings.getUserAgentString()+(BuildConfig.IS_GUARD?" VanRakshakGuard/1":" VanRakshakCommunity/1"));
        CookieManager.getInstance().setAcceptThirdPartyCookies(web,false);
        web.setWebViewClient(new WebViewClient(){
            @Override public boolean shouldOverrideUrlLoading(WebView view,WebResourceRequest request){
                if(trusted(request.getUrl().toString()))return false;
                if(request.isForMainFrame() && "https".equals(request.getUrl().getScheme()))try{startActivity(new Intent(Intent.ACTION_VIEW,request.getUrl()));}catch(ActivityNotFoundException ignored){}
                return true;
            }
            @Override public void onPageStarted(WebView v,String url,android.graphics.Bitmap icon){status.setText("Connecting…");}
            @Override public void onPageFinished(WebView v,String url){if(trusted(url)){status.setText("");PushSupport.attach(MainActivity.this);}}
            @Override public void onReceivedError(WebView v,WebResourceRequest r,WebResourceError e){if(r.isForMainFrame())status.setText("Connection unavailable. Check internet, then tap Retry.");}
            @Override public void onReceivedHttpError(WebView v,WebResourceRequest r,WebResourceResponse e){if(r.isForMainFrame())status.setText("Server unavailable. Tap Retry in a moment.");}
        });
        web.setWebChromeClient(new WebChromeClient(){
            @Override public void onGeolocationPermissionsShowPrompt(String origin,GeolocationPermissions.Callback cb){
                if(!trusted(origin)||!trusted(web.getUrl())){cb.invoke(origin,false,false);return;}
                if(locationCallback!=null)locationCallback.invoke(locationOrigin,false,false);
                locationCallback=cb;locationOrigin=origin;
                new AlertDialog.Builder(MainActivity.this).setTitle("Share your current location?").setMessage("Used to place your report or team on the map. You can select a map point instead.")
                .setNegativeButton("Use map",(d,w)->finishLocation(false)).setPositiveButton("Use location",(d,w)->{
                    if(hasLocation())finishLocation(true);else requestPermissions(new String[]{Manifest.permission.ACCESS_FINE_LOCATION,Manifest.permission.ACCESS_COARSE_LOCATION},10);
                }).setOnCancelListener(d->finishLocation(false)).show();
            }
            @Override public boolean onShowFileChooser(WebView v,ValueCallback<Uri[]> cb,FileChooserParams p){
                if(!trusted(v.getUrl()))return false;
                if(files!=null)files.onReceiveValue(null);files=cb;
                Intent i=new Intent(Intent.ACTION_GET_CONTENT);i.addCategory(Intent.CATEGORY_OPENABLE);i.setType("image/*");
                try{startActivityForResult(Intent.createChooser(i,"Choose a report photo"),11);}catch(ActivityNotFoundException e){files.onReceiveValue(null);files=null;}
                return true;
            }
        });
        PushSupport.setup(this);
        web.loadUrl(BuildConfig.BASE_URL+intentPath(getIntent()));
    }
    private boolean hasLocation(){return checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION)==PackageManager.PERMISSION_GRANTED||checkSelfPermission(Manifest.permission.ACCESS_COARSE_LOCATION)==PackageManager.PERMISSION_GRANTED;}
    private void finishLocation(boolean allow){if(locationCallback!=null){locationCallback.invoke(locationOrigin,allow&&trusted(web.getUrl()),false);locationCallback=null;}}
    private String homePath(){return BuildConfig.IS_GUARD?"/my-team":"/my-reports";}
    private String intentPath(Intent intent){String kind=intent.getStringExtra("incidentType"), id=intent.getStringExtra("incidentId");return BuildConfig.IS_GUARD && ("fire".equals(kind)||"conflict".equals(kind)) && id!=null && id.matches("[0-9]{1,18}")?"/incidents/"+kind+"/"+id:homePath();}
    @Override protected void onNewIntent(Intent intent){super.onNewIntent(intent);setIntent(intent);web.loadUrl(BuildConfig.BASE_URL+intentPath(intent));}
    @Override public void onRequestPermissionsResult(int code,String[] permissions,int[] results){super.onRequestPermissionsResult(code,permissions,results);if(code==10)finishLocation(hasLocation());if(code==12)PushSupport.attach(this);}
    @Override protected void onActivityResult(int code,int result,Intent data){super.onActivityResult(code,result,data);if(code==11&&files!=null){files.onReceiveValue(result==RESULT_OK&&data!=null&&data.getData()!=null?new Uri[]{data.getData()}:null);files=null;}}
    public void pushState(String token,String message){runOnUiThread(()->{if(trusted(web.getUrl()))web.evaluateJavascript("window.vanrakshakPush={token:"+JSONObject.quote(token)+",message:"+JSONObject.quote(message)+"};window.dispatchEvent(new Event('native-push-ready'));",null);});}
    @Override protected void onResume(){super.onResume();if(web!=null){web.onResume();PushSupport.attach(this);}}
    @Override protected void onPause(){if(web!=null){web.evaluateJavascript("window.dispatchEvent(new Event('native-app-paused'));",null);web.onPause();}super.onPause();}
    @Override protected void onDestroy(){finishLocation(false);if(files!=null)files.onReceiveValue(null);web.destroy();super.onDestroy();}
}
