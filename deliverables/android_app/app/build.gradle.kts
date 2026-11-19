plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("com.google.devtools.ksp")
}

android {
    namespace = "com.nequipos.agent"
    compileSdk = 34

    val releaseVersionCode = (project.findProperty("versionCode") as? String)?.toIntOrNull()
        ?: System.getenv("APP_VERSION_CODE")?.toIntOrNull()
        ?: 1
    val releaseVersionName = (project.findProperty("versionName") as? String)?.takeIf { it.isNotBlank() }
        ?: System.getenv("APP_VERSION_NAME")?.takeIf { it.isNotBlank() }
        ?: "1.0.0"

    defaultConfig {
        applicationId = "com.nequipos.agent"
        minSdk = 26
        targetSdk = 34
        versionCode = releaseVersionCode
        versionName = releaseVersionName
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
    }

    signingConfigs {
        create("release") {
            val keystorePath = (project.findProperty("keystorePath") as? String)
                ?: System.getenv("ANDROID_KEYSTORE_PATH")
            if (!keystorePath.isNullOrBlank() && file(keystorePath).exists()) {
                storeFile = file(keystorePath)
                storePassword = (project.findProperty("keystorePassword") as? String)
                    ?: System.getenv("ANDROID_KEYSTORE_PASSWORD")
                keyAlias = (project.findProperty("keyAlias") as? String)
                    ?: System.getenv("ANDROID_KEY_ALIAS")
                keyPassword = (project.findProperty("keyPassword") as? String)
                    ?: System.getenv("ANDROID_KEY_PASSWORD")
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
            val releaseConfig = signingConfigs.getByName("release")
            if (releaseConfig.storeFile != null) {
                signingConfig = releaseConfig
            }
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }
    buildFeatures {
        viewBinding = true
        buildConfig = true
    }
    testOptions {
        unitTests.isReturnDefaultValues = true
    }
}

dependencies {
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.appcompat:appcompat:1.7.0")
    implementation("com.google.android.material:material:1.12.0")

    // Room Database (Cola persistente offline)
    val roomVersion = "2.6.1"
    implementation("androidx.room:room-runtime:$roomVersion")
    implementation("androidx.room:room-ktx:$roomVersion")
    ksp("androidx.room:room-compiler:$roomVersion")

    // WorkManager (Sincronización cronológica garantizada al recuperar Wi-Fi)
    implementation("androidx.work:work-runtime-ktx:2.9.1")

    // Networking LAN HTTP
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    implementation("org.json:json:20240303")

    // Seguridad local (PIN + Token en EncryptedSharedPreferences)
    implementation("androidx.security:security-crypto:1.1.0-alpha06")

    // Escáner QR para configuración dinámica
    implementation("com.journeyapps:zxing-android-embedded:4.3.0")

    // Coroutines
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.8.1")

    // Pruebas Unitarias
    testImplementation("junit:junit:4.13.2")
}
