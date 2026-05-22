package com.example.h3client

import android.os.Bundle
import android.util.Log
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import com.example.h3client.databinding.ActivityMainBinding
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.chromium.net.CronetEngine
import org.chromium.net.CronetException
import org.chromium.net.UploadDataProviders
import org.chromium.net.UrlRequest
import org.chromium.net.UrlResponseInfo
import java.net.URI
import java.nio.ByteBuffer
import java.util.concurrent.Executors
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException
import kotlin.coroutines.suspendCoroutine

class MainActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMainBinding
    private lateinit var engine: CronetEngine
    private val executor = Executors.newSingleThreadExecutor()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        binding.baseUrl.setText(getString(R.string.default_base_url))
        engine = buildEngine(binding.baseUrl.text.toString())

        binding.btnHello.setOnClickListener { fire("GET", "/hello", null) }
        binding.btnInfo.setOnClickListener { fire("GET", "/info", null) }
        binding.btnEcho.setOnClickListener {
            fire("POST", "/echo", "ping from android at ${System.currentTimeMillis()}".toByteArray())
        }
    }

    override fun onDestroy() {
        engine.shutdown()
        executor.shutdown()
        super.onDestroy()
    }

    /**
     * Build a Cronet engine that prefers QUIC/H3 for the configured host so the
     * very first request goes out as HTTP/3 instead of upgrading from HTTP/2.
     */
    private fun buildEngine(baseUrl: String): CronetEngine {
        val uri = URI(baseUrl)
        val host = uri.host ?: "10.0.2.2"
        val port = if (uri.port > 0) uri.port else 443

        return CronetEngine.Builder(this)
            .enableHttp2(true)
            .enableQuic(true)
            .addQuicHint(host, port, port)
            // Force the QUIC version Cronet negotiates; "h3" is RFC 9114 (final).
            .setExperimentalOptions(
                """
                {
                  "QUIC": {
                    "host_whitelist": "$host",
                    "quic_version": "h3",
                    "max_server_configs_stored_in_properties": 2
                  }
                }
                """.trimIndent()
            )
            .setStoragePath(cacheDir.absolutePath)
            .enableHttpCache(CronetEngine.Builder.HTTP_CACHE_DISK_NO_HTTP, 1024L * 1024L)
            .build()
    }

    private fun fire(method: String, path: String, body: ByteArray?) {
        val url = binding.baseUrl.text.toString().trimEnd('/') + path
        binding.status.text = "→ $method $url"
        binding.output.text = ""
        lifecycleScope.launch {
            try {
                val result = withContext(Dispatchers.IO) { request(url, method, body) }
                binding.status.text =
                    "${result.statusCode} ${result.negotiatedProtocol} (${result.body.size}B)"
                binding.output.text = buildString {
                    append("HTTP ").append(result.statusCode).append('\n')
                    append("proto: ").append(result.negotiatedProtocol).append('\n')
                    append("rtt:   ").append(result.receivedByteCount).append("B received\n\n")
                    for ((k, v) in result.headers) {
                        append(k).append(": ").append(v).append('\n')
                    }
                    append('\n')
                    append(String(result.body))
                }
            } catch (e: Throwable) {
                Log.e(TAG, "request failed", e)
                binding.status.text = "ERROR: ${e.javaClass.simpleName}"
                binding.output.text = e.stackTraceToString()
            }
        }
    }

    private data class Result(
        val statusCode: Int,
        val negotiatedProtocol: String,
        val headers: List<Pair<String, String>>,
        val body: ByteArray,
        val receivedByteCount: Long,
    )

    private suspend fun request(url: String, method: String, body: ByteArray?): Result =
        suspendCoroutine { cont ->
            val sink = java.io.ByteArrayOutputStream()
            val callback = object : UrlRequest.Callback() {
                override fun onRedirectReceived(
                    request: UrlRequest, info: UrlResponseInfo, newLocationUrl: String
                ) {
                    request.followRedirect()
                }

                override fun onResponseStarted(request: UrlRequest, info: UrlResponseInfo) {
                    request.read(ByteBuffer.allocateDirect(32 * 1024))
                }

                override fun onReadCompleted(
                    request: UrlRequest, info: UrlResponseInfo, byteBuffer: ByteBuffer
                ) {
                    byteBuffer.flip()
                    val chunk = ByteArray(byteBuffer.remaining())
                    byteBuffer.get(chunk)
                    sink.write(chunk)
                    byteBuffer.clear()
                    request.read(byteBuffer)
                }

                override fun onSucceeded(request: UrlRequest, info: UrlResponseInfo) {
                    val headers = info.allHeadersAsList.map { it.key to it.value }
                    cont.resume(
                        Result(
                            statusCode = info.httpStatusCode,
                            negotiatedProtocol = info.negotiatedProtocol ?: "unknown",
                            headers = headers,
                            body = sink.toByteArray(),
                            receivedByteCount = info.receivedByteCount,
                        )
                    )
                }

                override fun onFailed(
                    request: UrlRequest, info: UrlResponseInfo?, error: CronetException
                ) {
                    cont.resumeWithException(error)
                }

                override fun onCanceled(request: UrlRequest, info: UrlResponseInfo?) {
                    cont.resumeWithException(RuntimeException("canceled"))
                }
            }

            val builder = engine.newUrlRequestBuilder(url, callback, executor)
                .setHttpMethod(method)

            if (body != null) {
                builder.addHeader("content-type", "application/octet-stream")
                builder.setUploadDataProvider(UploadDataProviders.create(body), executor)
            }

            builder.build().start()
        }

    companion object {
        private const val TAG = "H3Client"
    }
}
