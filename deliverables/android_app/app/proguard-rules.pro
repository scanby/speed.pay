# Reglas ProGuard / R8 para NequiPay POS Agente Android

-keepattributes SourceFile,LineNumberTable
-keepattributes *Annotation*,Signature,InnerClasses,EnclosingMethod

# Clases de dominio, Room y red
-keep class com.nequipos.agent.** { *; }
-keepclassmembers class * extends androidx.room.RoomDatabase {
    public <methods>;
}

# OkHttp & Okio
-dontwarn okhttp3.**
-dontwarn okio.**
-dontwarn javax.annotation.**
-dontwarn org.conscrypt.**
-dontwarn org.bouncycastle.**
-dontwarn org.openjsse.**

# Tink / AndroidX Security Crypto
-keepclassmembers class * extends com.google.crypto.tink.shaded.protobuf.GeneratedMessageLite { *; }
-dontwarn com.google.errorprone.annotations.**

# ZXing Barcode Scanner
-keep class com.journeyapps.barcodescanner.** { *; }
-keep class com.google.zxing.** { *; }
