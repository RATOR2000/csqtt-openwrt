plugins { id("com.android.application") }
android {
    namespace = "org.csqtt.openwrt.helper"
    compileSdk = 36
    defaultConfig {
        applicationId = "org.csqtt.openwrt.helper"
        minSdk = 28
        targetSdk = 36
        versionCode = 1
        versionName = "0.1.0-alpha.1"
    }
    compileOptions { sourceCompatibility = JavaVersion.VERSION_17; targetCompatibility = JavaVersion.VERSION_17 }
    signingConfigs {
        if (System.getenv("ANDROID_KEYSTORE") != null) {
            create("release") {
                storeFile = file(System.getenv("ANDROID_KEYSTORE"))
                storePassword = System.getenv("ANDROID_STORE_PASSWORD")
                keyAlias = System.getenv("ANDROID_KEY_ALIAS")
                keyPassword = System.getenv("ANDROID_KEY_PASSWORD")
            }
        }
    }
    buildTypes { getByName("release") { signingConfig = signingConfigs.findByName("release") } }
}
dependencies {
    implementation("androidx.webkit:webkit:1.14.0")
    testImplementation("junit:junit:4.13.2")
}
