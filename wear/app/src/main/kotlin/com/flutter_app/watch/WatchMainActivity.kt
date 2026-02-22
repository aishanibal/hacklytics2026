package com.flutter_app.watch

import android.content.Context
import android.os.Build
import android.os.Bundle
import android.os.VibrationEffect
import android.os.Vibrator
import android.view.WindowManager
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.core.animateDpAsState
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.MutableState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.Font
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.foundation.layout.size
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.wear.compose.material.Text
import kotlinx.coroutines.delay

enum class WatchState { IDLE, INCIDENT_DETECTED, INCIDENT_CONFIRMED }

// Palette
val IdleContent = Color(0xFF4F6367)      // 4f6367 - slate
val AlertRed = Color(0xFFFF8078)        // #ff8078
val ConfirmedBackground = Color(0xFFFEC0BC)  // #fec0bc
val ConfirmedBackgroundEnd = Color(0xFFFFDDDB)  // lighter for gradient
val White = Color.White

// Codec Pro: codec_pro_regular.ttf in res/font/
private val AppFont = FontFamily(Font(R.font.codec_pro_regular, FontWeight.Normal))

class WatchMainActivity : ComponentActivity() {
    private lateinit var vibrator: Vibrator

    // State lives in Activity so updates trigger Compose recomposition
    private val watchState = mutableStateOf(WatchState.IDLE)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        vibrator = getSystemService(Context.VIBRATOR_SERVICE) as Vibrator
        watchState.value = WatchState.IDLE
        setContent {
            WatchApp(
                vibrator = vibrator,
                stateHolder = watchState
            )
        }
    }
}

@Composable
fun WatchApp(
    vibrator: Vibrator,
    stateHolder: MutableState<WatchState>
) {
    var state by stateHolder
    val countdownState = remember { mutableStateOf(3) }
    val countdown by countdownState
    var secondsElapsed by remember { mutableStateOf(0) }
    val isRedState = remember { mutableStateOf(true) }
    var isRed by isRedState

    // Countdown 3 → 2 → 1 on idle, then trigger alert. Initial delay so first frame shows IDLE.
    LaunchedEffect(state) {
        if (state == WatchState.IDLE) {
            delay(150)
            countdownState.value = 3
            delay(1000)
            countdownState.value = 2
            delay(1000)
            countdownState.value = 1
            delay(1000)
            stateHolder.value = WatchState.INCIDENT_DETECTED
        }
    }

    LaunchedEffect(state) {
        if (state == WatchState.INCIDENT_DETECTED) {
            secondsElapsed = 0
            isRed = true
            // 20 × 500ms = 5 seconds: flash red / very light pink every 500ms, then auto-confirm
            repeat(20) {
                delay(500)
                isRed = !isRed
                if (it % 2 == 1) secondsElapsed = (it + 1) / 2
            }
            stateHolder.value = WatchState.INCIDENT_CONFIRMED
        }
    }

    LaunchedEffect(state) {
        when (state) {
            WatchState.IDLE -> vibrator.cancel()
            WatchState.INCIDENT_DETECTED -> {
                vibrator.cancel()
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                    vibrator.vibrate(
                        VibrationEffect.createWaveform(longArrayOf(0, 200, 100), 0)
                    )
                } else {
                    @Suppress("DEPRECATION")
                    vibrator.vibrate(longArrayOf(0, 200, 100), 0)
                }
            }
            WatchState.INCIDENT_CONFIRMED -> {
                vibrator.cancel()
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                    vibrator.vibrate(
                        VibrationEffect.createWaveform(longArrayOf(0, 500, 500), 0)
                    )
                } else {
                    @Suppress("DEPRECATION")
                    vibrator.vibrate(longArrayOf(0, 500, 500), 0)
                }
            }
        }
    }

    val activity = LocalContext.current as? ComponentActivity
    LaunchedEffect(state) {
        if (state == WatchState.IDLE) {
            activity?.window?.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        } else {
            activity?.window?.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        }
    }

    val backgroundBrush = when (state) {
        WatchState.IDLE -> Brush.verticalGradient(
            colors = listOf(Color.Black, Color(0xFF1B1B1B))
        )
        WatchState.INCIDENT_DETECTED -> if (isRed) {
            Brush.verticalGradient(colors = listOf(White, Color(0xFFFFE4E4)))  // lighter bg with red logo
        } else {
            Brush.verticalGradient(colors = listOf(ConfirmedBackgroundEnd, AlertRed))  // darker bg with white logo
        }
        WatchState.INCIDENT_CONFIRMED -> Brush.verticalGradient(
            colors = listOf(ConfirmedBackgroundEnd, AlertRed)
        )
    }

    val contentColor = when (state) {
        WatchState.IDLE -> IdleContent
        else -> White
    }

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(backgroundBrush),
        contentAlignment = Alignment.Center
    ) {
        AnimatedContent(
            targetState = state,
            transitionSpec = { fadeIn() togetherWith fadeOut() },
            label = "screen_transition"
        ) { targetState ->
            when (targetState) {
                WatchState.IDLE -> IdleScreen(
                    contentColor = contentColor,
                    countdownState = countdownState
                )
                WatchState.INCIDENT_DETECTED -> AlertScreen(
                    isRedState = isRedState,
                    onTripleTap = {
                        vibrator.cancel()
                        stateHolder.value = WatchState.IDLE
                    }
                )
                WatchState.INCIDENT_CONFIRMED -> ConfirmedScreen(
                    onDoubleTap = { stateHolder.value = WatchState.IDLE }
                )
            }
        }
    }
}

@Composable
fun IdleScreen(
    contentColor: Color,
    countdownState: MutableState<Int>
) {
    val countdown by countdownState
    Column(
        modifier = Modifier.fillMaxSize(),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center
    ) {
        Image(
            painter = painterResource(R.drawable.logo_blue),
            contentDescription = "Logo",
            modifier = Modifier.size(300.dp),
            contentScale = ContentScale.FillBounds
        )
    }
}

@Composable
fun AlertScreen(isRedState: MutableState<Boolean>, onTripleTap: () -> Unit) {
    val isRed by isRedState
    var tapCount by remember { mutableStateOf(0) }
    var lastTapTime by remember { mutableStateOf(0L) }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .pointerInput(Unit) {
                detectTapGestures {
                    val now = System.currentTimeMillis()
                    if (now - lastTapTime > 600) tapCount = 0
                    tapCount++
                    lastTapTime = now
                    if (tapCount >= 3) {
                        tapCount = 0
                        onTripleTap()
                    }
                }
            },
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center
    ) {
        Image(
            painter = painterResource(
                if (isRed) R.drawable.logo else R.drawable.logo_white
            ),
            contentDescription = "Alert",
            modifier = Modifier.size(300.dp),
            contentScale = ContentScale.FillBounds
        )
    }
}

@Composable
fun ConfirmedScreen(onDoubleTap: () -> Unit) {
    var tapCount by remember { mutableStateOf(0) }
    var lastTapTime by remember { mutableStateOf(0L) }
    var animationStarted by remember { mutableStateOf(false) }

    LaunchedEffect(Unit) { animationStarted = true }

    val logoSize by animateDpAsState(
        targetValue = if (animationStarted) 140.dp else 300.dp,
        animationSpec = tween(1200),
        label = "logoShrink"
    )
    val textAlpha by animateFloatAsState(
        targetValue = if (animationStarted) 1f else 0f,
        animationSpec = tween(800, delayMillis = 600),
        label = "textFade"
    )

    Box(
        modifier = Modifier
            .fillMaxSize()
            .pointerInput(Unit) {
                detectTapGestures {
                    val now = System.currentTimeMillis()
                    if (now - lastTapTime > 600) tapCount = 0
                    tapCount++
                    lastTapTime = now
                    if (tapCount >= 2) {
                        tapCount = 0
                        onDoubleTap()
                    }
                }
            },
        contentAlignment = Alignment.Center
    ) {
        Column(
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center
        ) {
            Image(
                painter = painterResource(R.drawable.logo),
                contentDescription = "Logo",
                modifier = Modifier.size(logoSize),
                contentScale = ContentScale.FillBounds
            )
            Text(
                "Help is arriving!",
                fontSize = 16.sp,
                fontFamily = AppFont,
                fontWeight = FontWeight.SemiBold,
                color = White,
                modifier = Modifier.alpha(textAlpha)
            )
        }
    }
}
