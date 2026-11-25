package ru.routerdash.android

import android.os.Bundle
import androidx.fragment.app.FragmentActivity
import androidx.biometric.BiometricManager
import androidx.biometric.BiometricPrompt
import androidx.core.content.ContextCompat
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.GridItemSpan
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.graphics.FilterQuality
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.res.imageResource
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.IntSize
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONObject
import java.net.URI
import java.util.concurrent.TimeUnit
import com.jcraft.jsch.JSch
import com.jcraft.jsch.ChannelShell
import com.jcraft.jsch.ChannelSftp
import com.jcraft.jsch.ChannelExec
import com.jcraft.jsch.Session
import java.io.InputStream
import java.io.ByteArrayOutputStream
import java.io.OutputStream

@Composable
private fun RouterDashIcon(index: Int, description: String?, modifier: Modifier = Modifier.size(40.dp)) {
    val atlas = ImageBitmap.imageResource(R.drawable.routerdash_icons_atlas)
    val cellSize = atlas.width / 4
    Canvas(modifier.semantics { contentDescription = description.orEmpty() }) {
        drawImage(
            image = atlas,
            srcOffset = IntOffset((index % 4) * cellSize, (index / 4) * cellSize),
            srcSize = IntSize(cellSize, cellSize),
            dstSize = IntSize(size.width.toInt(), size.height.toInt()),
            filterQuality = FilterQuality.Medium
        )
    }
}

class MainActivity : FragmentActivity() {
    private val securityPrefs by lazy { getSharedPreferences("routerdash_security", MODE_PRIVATE) }
    private val biometricUnlockSignal = androidx.compose.runtime.mutableIntStateOf(0)
    private val pickedSyncFolderUri = androidx.compose.runtime.mutableStateOf<String?>(null)
    private var shouldAuthenticate = true
    private var promptVisible = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent { RouterDashApp(biometricUnlockSignal.intValue, pickedSyncFolderUri.value, { pickSyncFolder() }, onEnableBiometric = { onEnabled -> enableBiometricLock(onEnabled) }) }
    }

    override fun onStart() {
        super.onStart()
        if (securityPrefs.getBoolean("biometric_enabled", false) && shouldAuthenticate) {
            authenticateBiometric()
        }
    }

    override fun onStop() {
        super.onStop()
        if (securityPrefs.getBoolean("biometric_enabled", false)) shouldAuthenticate = true
    }

    private val syncFolderRequestCode = 0x5244

    private fun pickSyncFolder() {
        val intent = android.content.Intent(android.content.Intent.ACTION_OPEN_DOCUMENT_TREE).apply {
            addFlags(android.content.Intent.FLAG_GRANT_READ_URI_PERMISSION or
                android.content.Intent.FLAG_GRANT_WRITE_URI_PERMISSION or
                android.content.Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION)
        }
        // Keep the request code in the platform's supported 16-bit range.
        startActivityForResult(intent, syncFolderRequestCode)
    }

    @Deprecated("Deprecated in Android API; bounded request code avoids registry overflow on affected devices")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: android.content.Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode == syncFolderRequestCode && resultCode == RESULT_OK) {
            val uri = data?.data ?: return
            val grantFlags = data.flags and
                (android.content.Intent.FLAG_GRANT_READ_URI_PERMISSION or android.content.Intent.FLAG_GRANT_WRITE_URI_PERMISSION)
            runCatching { contentResolver.takePersistableUriPermission(uri, grantFlags) }
            pickedSyncFolderUri.value = uri.toString()
        }
    }

    private fun enableBiometricLock(onEnabled: () -> Unit) {
        val manager = BiometricManager.from(this)
        val status = manager.canAuthenticate(BiometricManager.Authenticators.BIOMETRIC_STRONG)
        if (status != BiometricManager.BIOMETRIC_SUCCESS) {
            val message = when (status) {
                BiometricManager.BIOMETRIC_ERROR_NONE_ENROLLED -> "Сначала добавь отпечаток пальца в настройках телефона."
                BiometricManager.BIOMETRIC_ERROR_NO_HARDWARE -> "На устройстве нет поддерживаемого биометрического датчика."
                BiometricManager.BIOMETRIC_ERROR_HW_UNAVAILABLE -> "Датчик отпечатка сейчас недоступен."
                else -> "Биометрическая авторизация недоступна (код $status)."
            }
            android.widget.Toast.makeText(this, message, android.widget.Toast.LENGTH_LONG).show()
            return
        }
        showBiometricPrompt(
            title = "Включить вход по отпечатку",
            subtitle = "Подтверди личность, чтобы включить защиту RouterDash",
            onSuccess = {
                securityPrefs.edit().putBoolean("biometric_enabled", true).apply()
                shouldAuthenticate = false
                onEnabled()
                android.widget.Toast.makeText(this, "Защита отпечатком включена", android.widget.Toast.LENGTH_SHORT).show()
            }
        )
    }

    private fun authenticateBiometric() {
        if (promptVisible) return
        showBiometricPrompt(
            title = "Разблокировать RouterDash",
            subtitle = "Используй отпечаток пальца для продолжения",
            onSuccess = { shouldAuthenticate = false; biometricUnlockSignal.intValue++ },
            onFailure = { finish() }
        )
    }

    private fun showBiometricPrompt(
        title: String,
        subtitle: String,
        onSuccess: () -> Unit,
        onFailure: () -> Unit = {}
    ) {
        if (promptVisible) return
        promptVisible = true
        val executor = ContextCompat.getMainExecutor(this)
        val prompt = BiometricPrompt(this, executor, object : BiometricPrompt.AuthenticationCallback() {
            override fun onAuthenticationSucceeded(result: BiometricPrompt.AuthenticationResult) {
                promptVisible = false
                onSuccess()
            }
            override fun onAuthenticationError(errorCode: Int, errString: CharSequence) {
                promptVisible = false
                if (errorCode != BiometricPrompt.ERROR_NEGATIVE_BUTTON &&
                    errorCode != BiometricPrompt.ERROR_USER_CANCELED) onFailure()
                else if (securityPrefs.getBoolean("biometric_enabled", false)) finish()
            }
        })
        val info = BiometricPrompt.PromptInfo.Builder()
            .setTitle(title)
            .setSubtitle(subtitle)
            .setNegativeButtonText("Отмена")
            .setAllowedAuthenticators(BiometricManager.Authenticators.BIOMETRIC_STRONG)
            .build()
        prompt.authenticate(info)
    }
}

private enum class Screen(val title: String) {
    OVERVIEW("Обзор"), NETWORK("Сеть"), DEVICES("Устройства"), STORAGE("Диски"), PACKAGES("Пакеты"), DOWNLOADS("Загрузки"), SERVICES("Службы"), VPN("VPN"), FIREWALL("Firewall"), PROCESSES("Процессы"), SSH("SSH-терминал"), SYNC("Синхронизация"), LOGS("Журнал"), SETTINGS("Настройки")
}
private data class TrafficPoint(val rx: Long, val tx: Long)
private data class Snapshot(
    val board: JSONObject? = null, val info: JSONObject? = null,
    val network: JSONObject? = null, val wireless: JSONObject? = null, val devices: JSONObject? = null,
    val services: JSONObject? = null, val serviceDiagnostics: String? = null, val logs: JSONObject? = null,
    val storage: JSONArray? = null, val storageError: String? = null,
    val packages: JSONObject? = null, val downloads: JSONObject? = null,
    val vpnStatus: String? = null, val diskDetails: String? = null, val firewallRules: String? = null,
    val cpuRaw: String? = null, val networkDevices: JSONObject? = null,
    val processes: String? = null, val logsError: String? = null,
    val loadAverageRaw: String? = null, val temperatureC: Double? = null,
    val cpuPercent: Int? = null, val rxRate: Long? = null, val txRate: Long? = null,
    val trafficHistory: List<TrafficPoint> = emptyList(),
    val cpuHistory: List<Int> = emptyList()
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun RouterDashApp(biometricUnlockSignal: Int, pickedSyncFolderUri: String?, onPickSyncFolder: () -> Unit, onEnableBiometric: (() -> Unit) -> Unit) {
    val context = LocalContext.current
    val prefs = remember { context.getSharedPreferences("routerdash", 0) }
    val scope = rememberCoroutineScope()
    var url by rememberSaveable { mutableStateOf(prefs.getString("url", "http://192.168.1.1") ?: "") }
    var username by rememberSaveable { mutableStateOf("root") }
    var password by remember { mutableStateOf("") }
    var connected by remember { mutableStateOf(false) }
    var loading by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    var selected by rememberSaveable { mutableStateOf(Screen.OVERVIEW) }
    var refreshIntervalSeconds by rememberSaveable { mutableIntStateOf(prefs.getInt("refresh_interval", 5).coerceIn(3, 60)) }
    var biometricEnabled by remember { mutableStateOf(context.getSharedPreferences("routerdash_security", 0).getBoolean("biometric_enabled", false)) }
    var snapshot by remember { mutableStateOf(Snapshot()) }
    var previousCpu by remember { mutableStateOf<LongArray?>(null) }
    var previousTraffic by remember { mutableStateOf<LongArray?>(null) }
    var previousTrafficAt by remember { mutableLongStateOf(0L) }
    var api by remember { mutableStateOf<RouterApi?>(null) }
    var showNavigationSheet by remember { mutableStateOf(false) }
    var sshSession by remember { mutableStateOf<SshTerminal?>(null) }
    var sshConnected by remember { mutableStateOf(false) }
    var sshConnecting by remember { mutableStateOf(false) }
    var sshOutput by remember { mutableStateOf("RouterDash SSH · готов к подключению\n") }

    fun refresh(screen: Screen = selected) {
        val client = api ?: return
        scope.launch {
            loading = true
            error = null
            try {
                snapshot = withContext(Dispatchers.IO) {
                    when (screen) {
                        Screen.OVERVIEW -> snapshot.copy(
                            board = runCatching { client.call("system", "board") }.getOrDefault(JSONObject()),
                            info = runCatching { client.call("system", "info") }.getOrDefault(JSONObject()),
                            loadAverageRaw = runCatching { readUbusFile(client, "/proc/loadavg") }.getOrNull()
                                ?.takeIf { parseLoadAverage(it) != null }
                                ?: runCatching { sshSession?.execReadOnly("cat /proc/loadavg") }.getOrNull(),                            temperatureC = readRouterTemperature(client, sshSession),
                            cpuRaw = runCatching { readUbusFile(client, "/proc/stat") }.getOrNull()?.takeIf { it.contains("cpu ") }
                                ?: runCatching { sshSession?.execReadOnly("cat /proc/stat") }.getOrNull()
                                ?: runCatching { client.execReadOnly("cat", listOf("/proc/stat")) }.getOrNull(),
                            networkDevices = client.call("luci-rpc", "getNetworkDevices"),
                            storage = runCatching { parseDfOutput(client.execReadOnly("df", listOf("-kP"))) }.getOrNull()
                                ?.takeIf { it.length() > 0 }
                                ?: runCatching { sshSession?.execReadOnly("df -kP")?.let(::parseDfOutput) }.getOrNull(),
                            vpnStatus = runCatching {
                                client.execReadOnly("sh", listOf("-c",
                                    "echo VPN_PROCESSES; ps | grep -E \"tailscale|sing-box|xray|openvpn|wireguard\" | grep -v grep; " +
                                    "echo TUNNEL_INTERFACES; ip -o addr 2>/dev/null | grep -E \"tailscale|tun|wg|sing\" || true"))
                            }.getOrNull()?.takeIf { it.isNotBlank() }
                                ?: readVpnDiagnostics(sshSession)
                        )
                        Screen.NETWORK -> {
                            val ifaceDump = client.call("network.interface", "dump")
                            val radios = client.call("luci-rpc", "getWirelessDevices")
                            // Enrich each AP interface with associated stations, matching LuCI's iwinfo calls.
                            radios.keys().asSequence().toList().forEach { radioKey ->
                                val radio = radios.optJSONObject(radioKey) ?: return@forEach
                                val interfaces = radio.optJSONArray("interfaces") ?: return@forEach
                                for (index in 0 until interfaces.length()) {
                                    val wifiIface = interfaces.optJSONObject(index) ?: continue
                                    val ifname = wifiIface.optString("ifname")
                                    if (ifname.isBlank()) continue
                                    runCatching {
                                        val assoc = client.call("iwinfo", "assoclist", JSONObject().put("device", ifname))
                                        wifiIface.put("associations", assoc.optJSONArray("results") ?: JSONArray())
                                    }.onFailure {
                                        wifiIface.put("associations", JSONArray())
                                        wifiIface.put("association_error", it.message ?: "Недоступно")
                                    }
                                }
                            }
                            snapshot.copy(network = ifaceDump, wireless = radios)
                        }
                        Screen.DEVICES -> {
                            val leases = runCatching { client.call("luci-rpc", "getDHCPLeases") }.getOrDefault(JSONObject())
                            val leaseArray = findArray(leases, listOf("dhcp_leases", "leases", "results", "entries"))
                            val arpRaw = runCatching { readUbusFile(client, "/proc/net/arp") }.getOrNull().orEmpty()
                            val arp = JSONArray()
                            arpRaw.lineSequence().drop(1).forEach { row ->
                                val fields = row.trim().split(Regex("\\s+"))
                                if (fields.size >= 6 && fields[2] == "0x2") {
                                    arp.put(JSONObject().put("ipaddr", fields[0]).put("macaddr", fields[3]).put("device", fields[5]))
                                }
                            }
                            val combined = JSONObject().put("dhcp_leases", leaseArray)
                                .put("arp_entries", arp)
                            snapshot.copy(devices = combined)
                        }
                        Screen.STORAGE -> {
                            val failures = mutableListOf<String>()
                            var mounts = runCatching { normalizeMounts(client.callArray("luci", "getMountPoints")) }
                                .onFailure { failures += "luci.getMountPoints: ${it.message}" }.getOrDefault(JSONArray())
                            if (mounts.length() == 0) {
                                mounts = runCatching {
                                    normalizeMounts(findArrayDeep(client.call("luci", "getMountPoints"),
                                        listOf("mounts", "mount_points", "mountpoints", "results", "entries", "data")))
                                }.onFailure { failures += "ответ LuCI: ${it.message}" }.getOrDefault(JSONArray())
                            }
                            if (mounts.length() == 0) {
                                mounts = runCatching { parseDfOutput(client.execReadOnly("df", listOf("-kP"))) }
                                    .onFailure { failures += "df -kP: ${it.message}" }.getOrDefault(JSONArray())
                            }
                            if (mounts.length() == 0) {
                                mounts = runCatching { parseDfOutput(client.execReadOnly("df", listOf("-k"))) }
                                    .onFailure { failures += "df -k: ${it.message}" }.getOrDefault(JSONArray())
                            }
                            if (mounts.length() == 0) {
                                mounts = runCatching { parseProcMounts(readUbusFile(client, "/proc/mounts").orEmpty()) }
                                    .onFailure { failures += "/proc/mounts: ${it.message}" }.getOrDefault(JSONArray())
                            }
                            // SSH fallback is only used after an explicit connection in the SSH screen.
                            val sshDf = runCatching { sshSession?.execReadOnly("df -kP") }.getOrNull().orEmpty()
                            if (mounts.length() == 0 && sshDf.isNotBlank()) mounts = parseDfOutput(sshDf)
                            // Match LuCI's own storage page: system.info provides root and tmp
                            // capacities in KiB, while luci.getMountPoints provides mounted volumes in bytes.
                            runCatching {
                                val systemInfo = client.call("system", "info")
                                listOf("root" to "/", "tmp" to "/tmp").forEach { (key, mountPath) ->
                                    val fs = systemInfo.optJSONObject(key) ?: return@forEach
                                    val totalKb = fs.optLong("total")
                                    val usedKb = fs.optLong("used", -1L)
                                    val freeKb = fs.optLong("free", -1L)
                                    if (totalKb > 0L && mounts.toString().contains("\"mount\":\"$mountPath\"").not()) {
                                        val usedBytes = if (usedKb >= 0L) usedKb * 1024L
                                            else (totalKb - freeKb.coerceAtLeast(0L)) * 1024L
                                        mounts.put(JSONObject().put("device", if (key == "root") "rootfs" else "tmpfs")
                                            .put("mount", mountPath).put("size", totalKb * 1024L)
                                            .put("used", usedBytes).put("avail", (totalKb * 1024L - usedBytes).coerceAtLeast(0L)))
                                    }
                                }
                            }
                            fun readDiagnostic(label: String, command: String, args: List<String> = emptyList(), sshCommand: String = command + if (args.isEmpty()) "" else " " + args.joinToString(" ")): String {
                                val rpc = runCatching { client.execReadOnly(command, args) }
                                if (rpc.isSuccess && rpc.getOrNull().orEmpty().isNotBlank()) return rpc.getOrThrow()
                                val ssh = runCatching { sshSession?.execReadOnly(sshCommand) }
                                val sshOutput = ssh.getOrNull().orEmpty()
                                if (sshOutput.isNotBlank()) return sshOutput
                                val reason = rpc.exceptionOrNull()?.message ?: "пустой ответ"
                                failures += "$label: $reason" + (ssh.exceptionOrNull()?.message?.let { "; SSH: $it" } ?: "")
                                return "Недоступно: $reason"
                            }
                            val mountOutput = readDiagnostic("mount", "mount")
                            val mountedPaths = parseMountCommandOutput(mountOutput)
                            val knownMounts = (0 until mounts.length()).mapNotNull { mounts.optJSONObject(it)?.optString("mount") }.toSet()
                            for (mountIndex in 0 until mountedPaths.length()) {
                                val item = mountedPaths.optJSONObject(mountIndex) ?: continue
                                if (item.optString("mount") !in knownMounts) mounts.put(item)
                            }
                            val blockInfo = readDiagnostic("block info", "block", listOf("info"))
                            val deviceList = readDiagnostic("ls /dev", "ls", listOf("-l", "/dev"))
                            val sysBlock = readDiagnostic("ls /sys/block", "ls", listOf("-1", "/sys/block"))
                            val diskStats = readDiagnostic("/proc/diskstats", "cat", listOf("/proc/diskstats"))
                            val dfHuman = readDiagnostic("df -h", "df", listOf("-h"))
                            // Always merge df metrics, even when LuCI returned only root/tmp.
                            val dfOutput = readDiagnostic("df -kP (метрики файловых систем)", "df", listOf("-kP"))
                            val dfRows = if (dfOutput.startsWith("Недоступно:")) JSONArray() else parseDfOutput(dfOutput)
                            val mountIndexes = mutableMapOf<String, Int>()
                            for (index in 0 until mounts.length()) {
                                val path = mounts.optJSONObject(index)?.optString("mount").orEmpty()
                                if (path.isNotBlank()) mountIndexes[path] = index
                            }
                            for (index in 0 until dfRows.length()) {
                                val row = dfRows.optJSONObject(index) ?: continue
                                val path = row.optString("mount")
                                val existingIndex = mountIndexes[path]
                                if (existingIndex == null) {
                                    mounts.put(row)
                                    mountIndexes[path] = mounts.length() - 1
                                } else {
                                    val existing = mounts.optJSONObject(existingIndex) ?: JSONObject()
                                    listOf("device", "size", "used", "avail").forEach { key ->
                                        if (row.has(key)) existing.put(key, row.opt(key))
                                    }
                                    mounts.put(existingIndex, existing)
                                }
                            }
                            val knownAfterMerge = (0 until mounts.length()).mapNotNull { mounts.optJSONObject(it)?.optString("mount") }.toSet()
                            if ("/mnt/sda" !in knownAfterMerge && "/mnt/sda1" !in knownAfterMerge) {
                                failures += "SSD /mnt/sda не обнаружен среди точек монтирования."
                            }
                            val diagnostic = failures.joinToString("\n").ifBlank { null }
                            val diskDetails = buildString {
                                append("BLOCK INFO\n"); append(blockInfo)
                                append("\n\nФИЗИЧЕСКИЕ УСТРОЙСТВА\n"); append(deviceList)
                                append("\n\nРАЗДЕЛЫ /SYS/BLOCK\n"); append(sysBlock)
                                append("\n\nDISKSTATS\n"); append(diskStats)
                                append("\n\nMOUNT\n"); append(mountOutput.ifBlank { "Нет данных" })
                                append("\n\nDF -H\n"); append(dfHuman)
                            }
                            snapshot.copy(storage = mounts, storageError = diagnostic, diskDetails = diskDetails)
                        }
                        Screen.PACKAGES -> snapshot.copy(packages = client.call("rpc-sys", "packagelist"))
                        Screen.DOWNLOADS -> snapshot.copy(downloads = client.aria2Overview())
                        Screen.FIREWALL -> {
                            // Use rpcd UCI API and invoke nft directly. Never pass arbitrary shell
                            // text to file.exec: a shell executable in a read ACL is a security risk.
                            val uciResult = runCatching {
                                client.call("uci", "get", JSONObject().put("config", "firewall")).toString(2)
                            }
                            val nftResult = runCatching {
                                client.execReadOnly("nft", listOf("list", "ruleset"))
                            }
                            val statusResult = if (nftResult.isFailure) runCatching {
                                client.call("firewall", "status").toString(2)
                            } else Result.success("")
                            val firewallText = buildString {
                                append("UCI_FIREWALL\n")
                                append(uciResult.getOrElse { "Ошибка чтения UCI firewall: ${it.message}" })
                                append("\nNFT_RULESET\n")
                                append(nftResult.getOrElse {
                                    val status = statusResult.getOrNull().orEmpty()
                                    if (status.isNotBlank()) "nft недоступен через file.exec. Статус firewall:\n$status"
                                    else "Ошибка чтения nftables: ${it.message}"
                                })
                            }
                            snapshot.copy(firewallRules = firewallText)
                        }
                        Screen.VPN -> {
                            val rpcVpn = runCatching { client.execReadOnly("sh", listOf("-c",
                                "echo VPN_PROCESSES; ps | grep -E \"tailscale|sing-box|xray|openvpn|wireguard\" | grep -v grep; " +
                                "echo TUNNEL_INTERFACES; ip -o addr 2>/dev/null | grep -E \"tailscale|tun|wg|sing\" || true")) }
                                .getOrNull()?.takeIf { it.isNotBlank() }
                            snapshot.copy(vpnStatus = rpcVpn ?: readVpnDiagnostics(sshSession))
                        }
                        Screen.SERVICES, Screen.PROCESSES -> {
                            // /etc/init.d is the authoritative inventory; ubus supplies runtime state.
                            val serviceFailures = mutableListOf<String>()
                            val rcServices = runCatching { client.call("rc", "list") }
                                .onFailure { serviceFailures += "rc.list: ${it.message}" }
                                .getOrDefault(JSONObject())
                            val initServices = runCatching { client.call("luci", "getInitList") }
                                .onFailure { serviceFailures += "luci.getInitList: ${it.message}" }
                                .getOrNull()
                            val initNames = runCatching {
                                client.execReadOnly("ls", listOf("-1", "/etc/init.d"))
                                    .lineSequence().map { it.trim() }
                                    .filter { it.matches(Regex("[A-Za-z0-9_.-]+")) }.toList()
                            }.onFailure { serviceFailures += "ls /etc/init.d: ${it.message}" }
                                .getOrDefault(emptyList())
                            val sshInitNames = runCatching { sshSession?.execReadOnly("ls -1 /etc/init.d") }.getOrNull().orEmpty()
                                .lineSequence().map { it.trim() }
                                .filter { it.matches(Regex("[A-Za-z0-9_.-]+")) }.toList()
                            val mergedServices = normalizeServiceInventory(rcServices, initServices)
                            (initNames + sshInitNames).distinct().forEach { name ->
                                if (!mergedServices.has(name)) mergedServices.put(name, JSONObject())
                            }
                            val serviceNames = mergedServices.keys().asSequence().toList().toSet()
                            val topResult = runCatching { client.execReadOnly("top", listOf("-b", "-n", "1")) }
                            val topRpc = topResult.getOrNull()?.takeIf { it.isNotBlank() }
                                ?: runCatching { client.execReadOnly("busybox", listOf("top", "-b", "-n", "1")) }.getOrNull()
                            val topSsh = if (topRpc.isNullOrBlank()) runCatching { sshSession?.execReadOnly("top -b -n 1") }.getOrNull() else null
                            val topText = topRpc?.takeIf { it.isNotBlank() } ?: topSsh?.takeIf { it.isNotBlank() }
                                ?: "Не удалось получить top: ${topResult.exceptionOrNull()?.message ?: "file.exec недоступен"}" +
                                    if (sshSession == null) ". Подключи SSH в соответствующем разделе для получения процессов." else ""
                            val psRpc = runCatching { client.execReadOnly("ps", listOf("-o", "pid,comm,rss")) }
                                .recoverCatching { client.execReadOnly("ps") }
                                .recoverCatching { client.execReadOnly("ps", listOf("w")) }.getOrNull()
                            val psSsh = if (psRpc.isNullOrBlank()) runCatching { sshSession?.execReadOnly("ps -o pid,comm,rss") }.getOrNull() else null
                            val psText = psRpc?.takeIf { it.isNotBlank() } ?: psSsh?.takeIf { it.isNotBlank() }
                                ?: "Не удалось получить список процессов ps."
                            val processOutput = topText + "\n--ROUTERDASH-PS--\n" + psText
                            val serviceDiagnostics = buildList {
                                if (initNames.isEmpty() && sshInitNames.isEmpty()) add("Полный список /etc/init.d недоступен через LuCI RPC. Подключи SSH в разделе «SSH-терминал», чтобы получить полный инвентарь без изменения ACL.")
                                if (serviceNames.size < 10) add("Получено только ${serviceNames.size} имён служб; ожидается полный системный список.")
                                addAll(serviceFailures)
                            }.joinToString("\n").ifBlank { null }
                            snapshot.copy(services = mergedServices, serviceDiagnostics = serviceDiagnostics, processes = processOutput)
                        }
                        Screen.LOGS -> {
                            val args = JSONObject().put("lines", 300)
                            val failures = mutableListOf<String>()
                            var logs = runCatching { JSONObject().put("log", normalizeLogRows(client.callArray("log", "read", args))) }
                                .onFailure { failures += "ubus log.read (array): ${it.message}" }
                                .getOrDefault(JSONObject().put("log", JSONArray()))
                            if (logs.optJSONArray("log")?.length() == 0) {
                                logs = runCatching { normalizeLogResponse(client.call("log", "read", args)) }
                                    .onFailure { failures += "ubus log.read (object): ${it.message}" }
                                    .getOrDefault(JSONObject().put("log", JSONArray()))
                            }
                            if (logs.optJSONArray("log")?.length() == 0) {
                                logs = runCatching { parseLogReadOutput(client.execReadOnly("logread", listOf("-l", "300"))) }
                                    .onFailure { failures += "logread: ${it.message}" }
                                    .getOrDefault(JSONObject().put("log", JSONArray()))
                            }
                            val hasEntries = (logs.optJSONArray("log")?.length() ?: 0) > 0
                            snapshot.copy(logs = logs,
                                logsError = if (hasEntries) null else failures.joinToString("\n").ifBlank { null })                        }
                        Screen.SSH -> snapshot
                        Screen.SYNC -> snapshot
                        Screen.SETTINGS -> snapshot
                    }
                }
                if (screen == Screen.OVERVIEW) {
                    val ticks = parseCpuTicks(snapshot.cpuRaw)
                    val oldTicks = previousCpu
                    val cpu = if (ticks != null && oldTicks != null && ticks[0] > oldTicks[0]) {
                        val totalDelta = ticks[0] - oldTicks[0]
                        val idleDelta = ticks[1] - oldTicks[1]
                        (((totalDelta - idleDelta).coerceAtLeast(0L) * 100L) / totalDelta).toInt().coerceIn(0, 100)
                    } else null
                    if (ticks != null) previousCpu = ticks

                    val devices = snapshot.networkDevices
                    val wanStats = devices?.optJSONObject("eth1")?.optJSONObject("stats")
                    val counters = if (wanStats != null) longArrayOf(
                        wanStats.optLong("rx_bytes"), wanStats.optLong("tx_bytes")
                    ) else null
                    val now = System.currentTimeMillis()
                    val oldCounters = previousTraffic
                    val dt = (now - previousTrafficAt).coerceAtLeast(1L)
                    val rx = if (counters != null && oldCounters != null && counters[0] >= oldCounters[0])
                        ((counters[0] - oldCounters[0]) * 1000L / dt) else null
                    val tx = if (counters != null && oldCounters != null && counters[1] >= oldCounters[1])
                        ((counters[1] - oldCounters[1]) * 1000L / dt) else null
                    if (counters != null) {
                        previousTraffic = counters
                        previousTrafficAt = now
                    }
                    if (cpu != null || rx != null || tx != null) {
                        val history = if (rx != null && tx != null)
                            (snapshot.trafficHistory + TrafficPoint(rx, tx)).takeLast(36)
                        else snapshot.trafficHistory
                        val cpuHistory = if (cpu != null)
                            (snapshot.cpuHistory + cpu).takeLast(48) else snapshot.cpuHistory
                        snapshot = snapshot.copy(cpuPercent = cpu ?: snapshot.cpuPercent,
                            rxRate = rx, txRate = tx, trafficHistory = history, cpuHistory = cpuHistory)
                    }
                }
                if (screen == Screen.OVERVIEW) {
                    saveRouterDashWidgetSnapshot(context, snapshot, url)
                }
            } catch (e: Exception) {
                error = e.message ?: "Ошибка получения данных"
                if (error?.contains("401") == true || error?.contains("403") == true) connected = false
                if (screen == Screen.OVERVIEW) {
                    context.getSharedPreferences("routerdash_widget_cache", 0).edit()
                        .putBoolean("online", false).putLong("updated_at", System.currentTimeMillis()).apply()
                    RouterDashWidgetProvider.refreshAll(context)
                }
            } finally { loading = false }
        }
    }

    fun connect() {
        val parsed = runCatching { URI(url.trim()) }.getOrNull()
        if (parsed?.host.isNullOrBlank() || parsed?.scheme !in listOf("http", "https") || parsed?.userInfo != null) {
            error = "Укажи корректный адрес, например http://192.168.1.1"; return
        }
        scope.launch {
            loading = true; error = null
            try {
                val newApi = RouterApi(url.trim().trimEnd('/'))
                withContext(Dispatchers.IO) { newApi.login(username.trim(), password) }
                api = newApi
                prefs.edit().putString("url", newApi.baseUrl).apply()
                runCatching { encryptedCredentials(context).edit().putString("url", newApi.baseUrl).putString("username", username.trim()).putString("password", password).apply() }
                connected = true
                password = ""
                refresh(Screen.OVERVIEW)
            } catch (e: Exception) {
                error = e.message ?: "Не удалось подключиться"; connected = false
            } finally { loading = false }
        }
    }

    LaunchedEffect(biometricUnlockSignal) {
        if (biometricUnlockSignal > 0 && !connected) {
            runCatching {
                val saved = encryptedCredentials(context)
                val savedUrl = saved.getString("url", null)
                val savedUser = saved.getString("username", null)
                val savedPassword = saved.getString("password", null)
                if (!savedUrl.isNullOrBlank() && !savedUser.isNullOrBlank() && !savedPassword.isNullOrBlank()) {
                    url = savedUrl; username = savedUser; password = savedPassword; connect()
                } else error = "Нет сохранённых данных входа. Подключись по паролю один раз, затем вход по отпечатку будет автоматическим."
            }.onFailure { error = "Не удалось открыть защищённые данные входа: " + (it.message ?: "ошибка") }
        }
    }

    LaunchedEffect(sshConnected) {
        while (sshConnected) {
            val chunk = withContext(Dispatchers.IO) {
                runCatching { sshSession?.readAvailable().orEmpty() }.getOrDefault("")
            }
            if (chunk.isNotEmpty()) sshOutput = (sshOutput + chunk).takeLast(24000)
            delay(250)
        }
    }

    LaunchedEffect(connected, selected, refreshIntervalSeconds) {
        while (connected) {
            refresh(selected)
            delay(refreshIntervalSeconds * 1000L)
        }
    }

    val screenWidthDp = LocalConfiguration.current.screenWidthDp
    val isExpandedLayout = screenWidthDp >= 600

    MaterialTheme(colorScheme = darkColorScheme(
        primary = androidx.compose.ui.graphics.Color(0xFFFF784E),
        secondary = androidx.compose.ui.graphics.Color(0xFF47D7FF),
        tertiary = androidx.compose.ui.graphics.Color(0xFFA98BFF),
        background = androidx.compose.ui.graphics.Color(0xFF0C1320),
        surface = androidx.compose.ui.graphics.Color(0xFF172235),
        surfaceVariant = androidx.compose.ui.graphics.Color(0xFF21314A),
        onBackground = androidx.compose.ui.graphics.Color(0xFFF4F6F8),
        onSurface = androidx.compose.ui.graphics.Color(0xFFF4F6F8),
        onSurfaceVariant = androidx.compose.ui.graphics.Color(0xFF9AA5B1)
    )) {
        if (!connected) {
            LoginScreen(url, { url = it }, username, { username = it }, password, { password = it },
                loading, error, ::connect)
        } else {
            Scaffold(
                topBar = {
                    TopAppBar(
                        title = {
                            Row(verticalAlignment = Alignment.CenterVertically,
                                horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                Icon(painterResource(R.drawable.ic_routerdash_foreground), null,
                                    tint = androidx.compose.ui.graphics.Color.Unspecified, modifier = Modifier.size(34.dp))
                                Column {
                                    Text("RouterDash", fontWeight = FontWeight.Bold)
                                    Text(url, style = MaterialTheme.typography.labelSmall,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant)
                                }
                            }
                        },
                        actions = {
                            IconButton(onClick = { selected = Screen.SETTINGS }) {
                                Icon(Icons.Outlined.Settings, contentDescription = "Настройки приложения")
                            }
                            if (loading) CircularProgressIndicator(Modifier.size(20.dp))
                            IconButton(onClick = { refresh() }) { Text("↻", style = MaterialTheme.typography.headlineSmall) }
                            IconButton(onClick = { scope.launch { withContext(Dispatchers.IO) { sshSession?.close() }; sshSession = null; sshConnected = false }; connected = false; api = null; selected = Screen.OVERVIEW }) {
                                Icon(Icons.Outlined.Logout, contentDescription = "Отключиться")
                            }
                        }
                    )
                },
                bottomBar = {
                    if (!isExpandedLayout) {
                        Surface(color = MaterialTheme.colorScheme.surface, tonalElevation = 5.dp) {
                            Row(Modifier.fillMaxWidth().navigationBarsPadding().padding(horizontal = 16.dp, vertical = 8.dp),
                                verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                                IconButton(onClick = { refresh() }, enabled = !loading) {
                                    Icon(Icons.Outlined.Refresh, contentDescription = "Обновить")
                                }
                                Button(onClick = { showNavigationSheet = true },
                                    modifier = Modifier.weight(1f).height(48.dp),
                                    shape = androidx.compose.foundation.shape.RoundedCornerShape(18.dp)) {
                                    Icon(Icons.Outlined.Menu, contentDescription = null)
                                    Spacer(Modifier.width(10.dp))
                                    Text("Разделы · ${selected.title}")
                                    Spacer(Modifier.weight(1f))
                                    Icon(Icons.Outlined.ExpandLess, contentDescription = null)
                                }
                            }
                        }
                    }
                }
            ) { padding ->
                Row(Modifier.fillMaxSize().padding(padding)) {
                    if (isExpandedLayout) {
                        NavigationRail(
                            containerColor = MaterialTheme.colorScheme.surface,
                            header = {
                                RouterDashIcon(0, "RouterDash", Modifier.padding(vertical = 12.dp).size(48.dp))
                            }
                        ) {
                            val entries = listOf(
                                Screen.OVERVIEW to 1,
                                Screen.NETWORK to 2,
                                Screen.DEVICES to 3,
                                Screen.STORAGE to 4,
                                Screen.PACKAGES to 5,
                                Screen.DOWNLOADS to 6,
                                Screen.SERVICES to 7,
                                Screen.PROCESSES to 14,
                                Screen.VPN to 8,
                                Screen.FIREWALL to 9,
                                Screen.SSH to 10,
                                Screen.SYNC to 11,
                                Screen.LOGS to 12,
                                Screen.SETTINGS to 13
                            )
                            entries.forEach { (screen, iconIndex) ->
                                NavigationRailItem(
                                    selected = selected == screen,
                                    onClick = { selected = screen; refresh(screen) },
                                    icon = { RouterDashIcon(iconIndex, screen.title) },
                                    label = { Text(screen.title, maxLines = 1) },
                                    alwaysShowLabel = false
                                )
                            }
                        }
                    }
                    Column(
                        Modifier.weight(1f).fillMaxHeight().widthIn(max = 1440.dp)
                            .padding(horizontal = if (isExpandedLayout) 28.dp else 16.dp)
                    ) {
                    // Show the supplied reference icon inside the active section, not only in navigation.
                    Row(
                        Modifier.fillMaxWidth().padding(top = 10.dp, bottom = 12.dp),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(12.dp)
                    ) {
                        RouterDashIcon(selected.ordinal + 1, selected.title, Modifier.size(56.dp))
                        Text(selected.title, style = MaterialTheme.typography.headlineSmall,
                            fontWeight = FontWeight.Bold)
                    }
                    HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.45f))
                    if (error != null) {
                        ElevatedCard(Modifier.fillMaxWidth().padding(top = 8.dp)) {
                            Text(error!!, Modifier.padding(12.dp), color = MaterialTheme.colorScheme.error)
                        }
                    }
                    when (selected) {
                        Screen.OVERVIEW -> OverviewScreen(snapshot)
                        Screen.NETWORK -> NetworkScreen(snapshot.network, snapshot.wireless)
                        Screen.DEVICES -> DevicesScreen(snapshot.devices, snapshot.wireless)
                        Screen.STORAGE -> StorageScreen(snapshot.storage, snapshot.storageError, snapshot.diskDetails) { refresh(Screen.STORAGE) }
                        Screen.PACKAGES -> PackagesScreen(snapshot.packages) { refresh(Screen.PACKAGES) }
                        Screen.DOWNLOADS -> DownloadsScreen(snapshot.downloads, api) { refresh(Screen.DOWNLOADS) }
                        Screen.SERVICES -> ServicesScreen(snapshot.services, snapshot.processes, snapshot.serviceDiagnostics, api) { refresh(Screen.SERVICES) }
                        Screen.PROCESSES -> ProcessesScreen(snapshot.processes) { refresh(Screen.PROCESSES) }
                        Screen.VPN -> VpnScreen(snapshot.vpnStatus) { refresh(Screen.VPN) }
                        Screen.FIREWALL -> FirewallScreen(snapshot.firewallRules) { refresh(Screen.FIREWALL) }
                        Screen.SYNC -> SyncScreen(
                            sshConnected = sshConnected,
                            ssh = sshSession,
                            sshHostDefault = runCatching { URI(url).host ?: "192.168.1.1" }.getOrDefault("192.168.1.1"),
                            sshUserDefault = username,
                            onOpenSsh = { selected = Screen.SSH },
                            pickedFolderUri = pickedSyncFolderUri,                            onPickFolder = onPickSyncFolder
                        )
                        Screen.SSH -> SshScreen(
                            host = runCatching { URI(url).host ?: "192.168.1.1" }.getOrDefault("192.168.1.1"),
                            defaultUser = username, connected = sshConnected, connecting = sshConnecting, output = sshOutput,
                            onConnect = { host, port, user, pass ->
                                scope.launch {
                                    sshConnecting = true
                                    try {
                                        val terminal = withContext(Dispatchers.IO) { SshTerminal(context).also { it.connect(host, port, user, pass) } }
                                        sshSession = terminal; sshConnected = true
                                        sshOutput += "\n[SSH] Соединение установлено: $user@$host:$port\n[SSH] Host key: ${terminal.fingerprint}\n"
                                    } catch (e: Exception) { sshOutput += "\n[SSH ERROR] ${e.message}\n" }
                                    finally { sshConnecting = false }
                                }
                            },
                            onSend = { command -> scope.launch {
                                try { withContext(Dispatchers.IO) { sshSession?.send(command) }; sshOutput += "\n$ $command\n" }
                                catch (e: Exception) { sshOutput += "\n[SSH ERROR] ${e.message}\n" }
                            } },
                            onDisconnect = { scope.launch {
                                withContext(Dispatchers.IO) { sshSession?.close() }
                                sshSession = null; sshConnected = false; sshOutput += "\n[SSH] Сессия закрыта\n"
                            } }
                        )
                        Screen.LOGS -> LogsScreen(snapshot.logs, snapshot.logsError)
                        Screen.SETTINGS -> SettingsScreen(
                            refreshIntervalSeconds = refreshIntervalSeconds,
                            onIntervalChange = { value ->
                                refreshIntervalSeconds = value
                                prefs.edit().putInt("refresh_interval", value).apply()
                            },
                            biometricEnabled = biometricEnabled,
                            onBiometricToggle = { enabled ->
                                if (enabled) {
                                    onEnableBiometric { biometricEnabled = true }
                                } else {
                                    context.getSharedPreferences("routerdash_security", 0).edit().putBoolean("biometric_enabled", false).apply()
                                    biometricEnabled = false
                                }
                            },
                            onDisconnect = { scope.launch { withContext(Dispatchers.IO) { sshSession?.close() }; sshSession = null; sshConnected = false }; connected = false; api = null; selected = Screen.OVERVIEW }
                        )
                    }
                    }
                    if (!isExpandedLayout && showNavigationSheet) {
                        val destinations = listOf(
                            Screen.OVERVIEW to 1,
                            Screen.NETWORK to 2,
                            Screen.DEVICES to 3,
                            Screen.STORAGE to 4,
                            Screen.PACKAGES to 5,
                            Screen.DOWNLOADS to 6,
                            Screen.SERVICES to 7,
                            Screen.PROCESSES to 14,
                            Screen.VPN to 8,
                            Screen.FIREWALL to 9,
                            Screen.SSH to 10,
                            Screen.SYNC to 11,
                            Screen.LOGS to 12,
                            Screen.SETTINGS to 13
                        )
                        ModalBottomSheet(onDismissRequest = { showNavigationSheet = false },
                            sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true),
                            containerColor = MaterialTheme.colorScheme.surface) {
                            Column(Modifier.fillMaxWidth().padding(horizontal = 16.dp)) {
                                Text("Навигация", style = MaterialTheme.typography.titleLarge,
                                    fontWeight = FontWeight.Bold, modifier = Modifier.padding(bottom = 10.dp))
                                LazyColumn(Modifier.heightIn(max = 560.dp)) {
                                    items(destinations) { (screen, iconIndex) ->
                                        NavigationDrawerItem(
                                            label = { Text(screen.title) }, selected = selected == screen,
                                            onClick = { showNavigationSheet = false; selected = screen; refresh(screen) },
                                            icon = { RouterDashIcon(iconIndex, null, Modifier.size(40.dp)) },
                                            modifier = Modifier.padding(vertical = 3.dp),
                                            shape = androidx.compose.foundation.shape.RoundedCornerShape(16.dp)
                                        )
                                    }
                                }
                                Spacer(Modifier.height(16.dp))
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun LoginScreen(
    url: String, onUrl: (String) -> Unit, username: String, onUsername: (String) -> Unit,
    password: String, onPassword: (String) -> Unit, loading: Boolean, error: String?, onConnect: () -> Unit
) {
    Box(Modifier.fillMaxSize().padding(24.dp), contentAlignment = Alignment.Center) {
        Card(Modifier.fillMaxWidth().widthIn(max = 480.dp)) {
            Column(Modifier.padding(24.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
                Text("RouterDash", style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Bold)
                Text("Нативное управление OpenWrt", color = MaterialTheme.colorScheme.onSurfaceVariant)
                OutlinedTextField(url, onUrl, Modifier.fillMaxWidth(), label = { Text("Адрес роутера") }, singleLine = true)
                OutlinedTextField(username, onUsername, Modifier.fillMaxWidth(), label = { Text("Пользователь") }, singleLine = true)
                OutlinedTextField(password, onPassword, Modifier.fillMaxWidth(), label = { Text("Пароль LuCI") },
                    singleLine = true, visualTransformation = PasswordVisualTransformation())
                if (error != null) Text(error, color = MaterialTheme.colorScheme.error)
                Button(onClick = onConnect, Modifier.fillMaxWidth(), enabled = !loading) {
                    if (loading) CircularProgressIndicator(Modifier.size(18.dp), strokeWidth = 2.dp)
                    else Text("Подключиться")
                }
                Text("Для быстрого повторного входа адрес и учётные данные сохраняются в зашифрованном хранилище Android.",
                    style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                if (url.trim().startsWith("http://", ignoreCase = true)) {
                    Text("Соединение HTTP не шифрует пароль и данные управления в сети. Используй HTTPS с доверенным сертификатом или защищённую VPN/локальную сеть.",
                        style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error)
                }
            }
        }
    }
}


@Composable
private fun SettingsScreen(
    refreshIntervalSeconds: Int,
    onIntervalChange: (Int) -> Unit,
    biometricEnabled: Boolean,
    onBiometricToggle: (Boolean) -> Unit,
    onDisconnect: () -> Unit
) {
    LazyColumn(contentPadding = PaddingValues(vertical = 16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item {
            Text("Настройки", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
            Text("Параметры работы RouterDash на этом устройстве",
                color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.bodySmall)
        }
        item {
            InfoCard("Частота обновления") {
                Text("Как часто приложение запрашивает данные у роутера.",
                    color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.bodySmall)
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    listOf(3, 5, 10, 15, 30, 60).forEach { seconds ->
                        FilterChip(selected = refreshIntervalSeconds == seconds,
                            onClick = { onIntervalChange(seconds) }, label = { Text("${seconds}с") })
                    }
                }
                Text("Текущий интервал: $refreshIntervalSeconds сек.",
                    style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.primary)
            }
        }
        item {
            InfoCard("Защита приложения") {
                Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        Text("Вход по отпечатку")
                        Text(if (biometricEnabled) "Защита включена" else "Защита выключена",
                            style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                    Switch(checked = biometricEnabled, onCheckedChange = onBiometricToggle)
                }
                Text("Используется системная биометрия Android.",
                    style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
        item {
            InfoCard("Подключение") {
                Text("Адрес, имя пользователя и пароль LuCI хранятся в зашифрованном хранилище Android Keystore.",
                    style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                OutlinedButton(onClick = onDisconnect, modifier = Modifier.fillMaxWidth()) {
                    Icon(Icons.Outlined.Logout, contentDescription = null)
                    Spacer(Modifier.width(8.dp))
                    Text("Отключиться от роутера")
                }
            }
        }
        item {
            InfoCard("Конфиденциальность") {
                Text("RouterDash работает напрямую с выбранным роутером. Подробно о сетевых запросах, локальном хранении учётных данных и удалении данных — в политике конфиденциальности.",
                    style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                val uriHandler = LocalUriHandler.current
                TextButton(onClick = {
                    uriHandler.openUri("https://github.com/pozakonstantin-sketch/luci-app-routerdash/blob/main/docs/privacy-policy.md")
                }) {
                    Icon(Icons.Outlined.Policy, contentDescription = null)
                    Spacer(Modifier.width(8.dp))
                    Text("Политика конфиденциальности")
                }
            }
        }
        item {
            Text("RouterDash ${BuildConfig.VERSION_NAME} · Нативное приложение", modifier = Modifier.fillMaxWidth().padding(top = 8.dp),
                style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

@Composable
private fun OverviewScreen(s: Snapshot) {
    val board = s.board
    val info = s.info
    val mem = info?.optJSONObject("memory")
    val total = mem?.optLong("total") ?: 0L
    val available = mem?.optLong("available", -1L)?.takeIf { it >= 0L }
        ?: ((mem?.optLong("free") ?: 0L) + (mem?.optLong("buffered") ?: 0L) + (mem?.optLong("cached") ?: 0L))
    val used = (total - available).coerceAtLeast(0L)
    val ramPercent = if (total > 0L) (used.toFloat() / total).coerceIn(0f, 1f) else 0f
    val uptime = info?.optLong("uptime")?.let { duration(it) } ?: "—"
    val loadValues = info?.optJSONArray("load")
    val load = parseLoadAverage(s.loadAverageRaw) ?: if (loadValues != null && loadValues.length() >= 3) {
        (0..2).joinToString(" / ") { index ->
            String.format(java.util.Locale.US, "%.2f", loadValues.optLong(index) / 65536.0)
        }
    } else "—"
    val hostname = board?.optString("hostname", "OpenWrt")?.ifBlank { "OpenWrt" } ?: "OpenWrt"
    val model = board?.optString("model", "Маршрутизатор")?.ifBlank { "Маршрутизатор" } ?: "Маршрутизатор"
    val cpu = s.cpuPercent
    val ramLabel = if (total > 0L) "${(ramPercent * 100).toInt()}%" else "—"
    val health = when {
        cpu == null || total <= 0L -> "Собираем данные"
        cpu >= 85 || ramPercent >= 0.90f -> "Нужна проверка"
        else -> "Всё работает"
    }
    val healthColor = if (health == "Нужна проверка")
        androidx.compose.ui.graphics.Color(0xFFFFB454)
    else androidx.compose.ui.graphics.Color(0xFF42D9A0)
    val diskRows = s.storage
    val rootDisk = (0 until (diskRows?.length() ?: 0)).mapNotNull { diskRows?.optJSONObject(it) }
        .firstOrNull { it.optString("mount") in listOf("/overlay", "/", "/mnt/sda") }
    val diskTotal = rootDisk?.optLong("size") ?: 0L
    val diskUsed = rootDisk?.optLong("used") ?: 0L
    val diskPercent = if (diskTotal > 0L) (diskUsed * 100L / diskTotal).toInt() else -1
    val vpn = s.vpnStatus.orEmpty()
    val vpnProcesses = vpn.substringAfter("VPN_PROCESSES", "").substringBefore("TAILSCALE_STATUS")
    val vpnDetected = vpnProcesses.contains("tailscale", true) || vpnProcesses.contains("sing-box", true) ||
        vpnProcesses.contains("xray", true) || vpnProcesses.contains("openvpn", true) || vpnProcesses.contains("wireguard", true)
    val vpnLabel = when {
        vpn.contains("Logged out", true) || vpn.contains("NeedsLogin", true) -> "Нужен вход"
        vpnDetected -> "Обнаружен"
        vpn.isBlank() -> "Проверяем…"
        else -> "Не найден"
    }
    LazyVerticalGrid(
        columns = GridCells.Fixed(2),
        userScrollEnabled = false,
        contentPadding = PaddingValues(horizontal = 3.dp, vertical = 4.dp),
        horizontalArrangement = Arrangement.spacedBy(7.dp),
        verticalArrangement = Arrangement.spacedBy(7.dp)
    ) {
        item(span = { GridItemSpan(maxLineSpan) }) {
            RouterStatusHero(hostname, model, health, healthColor, uptime)
        }
        item {            GaugeCard("CPU", cpu?.let { "$it%" } ?: "—",
                (cpu ?: 0) / 100f, "Процессор",
                accent = androidx.compose.ui.graphics.Color(0xFFFF8A3D))
        }
        item {
            GaugeCard("RAM", ramLabel, ramPercent,
                if (total > 0L) "Свободно ${formatBytes(available)}" else "Нет данных",
                accent = androidx.compose.ui.graphics.Color(0xFF4FBEFF))
        }
        item(span = { GridItemSpan(maxLineSpan) }) {
            InfoCard("Интернет · WAN") {
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                    DashboardMetric("↓ Приём", s.rxRate?.let { formatRate(it) } ?: "—",
                        androidx.compose.ui.graphics.Color(0xFF36D6C5), Modifier.weight(1f))
                    DashboardMetric("↑ Передача", s.txRate?.let { formatRate(it) } ?: "—",
                        androidx.compose.ui.graphics.Color(0xFFFF9A52), Modifier.weight(1f))
                    DashboardMetric("Load average", load,
                        androidx.compose.ui.graphics.Color(0xFFB58CFF), Modifier.weight(0.8f))
                }
            }
        }
        item {
            DashboardMiniCard("Температура CPU", s.temperatureC?.let { String.format(java.util.Locale.US, "%.1f °C", it) } ?: "Нет датчика",
                "Датчик thermal/hwmon", androidx.compose.ui.graphics.Color(0xFFFFB454), Icons.Outlined.DeviceThermostat)
        }
        item {
            DashboardMiniCard("Диск / overlay", if (diskPercent >= 0) "${diskPercent}%" else "—",
                if (diskTotal > 0) "${formatBytes(diskUsed)} / ${formatBytes(diskTotal)}" else "Нет данных",
                if (diskPercent >= 90) androidx.compose.ui.graphics.Color(0xFFFF5D73) else androidx.compose.ui.graphics.Color(0xFF55D6A7),
                Icons.Outlined.Storage)
        }
        item {
            DashboardMiniCard("VPN / туннели", vpnLabel,
                if (vpn.contains("Logged out", true)) "Tailscale: нет входа" else "Tailscale · sing-box · VLESS",
                if (vpnLabel == "Нужен вход") androidx.compose.ui.graphics.Color(0xFFFFB454) else androidx.compose.ui.graphics.Color(0xFF5CC8FF),
                Icons.Outlined.VpnKey)
        }
        item(span = { GridItemSpan(maxLineSpan) }) {
            InfoCard("Система · ${board?.optJSONObject("release")?.optString("version", "OpenWrt") ?: "OpenWrt"}") {
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                    CompactSystemMetric("Ядро", board?.optString("kernel", "—") ?: "—", Modifier.weight(1f))
                    CompactSystemMetric("Архитектура", board?.optString("system", "—") ?: "—", Modifier.weight(1f))
                    CompactSystemMetric("Аптайм", uptime, Modifier.weight(1f))
                }
            }
        }
        item(span = { GridItemSpan(maxLineSpan) }) {
            val warning = (cpu ?: 0) >= 85 || (total > 0L && ramPercent >= 0.90f) || diskPercent >= 90
            Surface(
                color = (if (warning) androidx.compose.ui.graphics.Color(0xFFFFB454) else androidx.compose.ui.graphics.Color(0xFF42D9A0)).copy(alpha = 0.12f),
                shape = androidx.compose.foundation.shape.RoundedCornerShape(15.dp),
                modifier = Modifier.fillMaxWidth()
            ) {
                Row(Modifier.padding(horizontal = 12.dp, vertical = 9.dp),
                    verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Icon(if (warning) Icons.Outlined.WarningAmber else Icons.Outlined.Verified,
                        null, tint = if (warning) androidx.compose.ui.graphics.Color(0xFFFFB454) else androidx.compose.ui.graphics.Color(0xFF42D9A0))
                    Text(if (warning) "Есть показатели, требующие внимания" else "Роутер работает штатно · критичных отклонений нет",
                        style = MaterialTheme.typography.labelMedium, fontWeight = FontWeight.SemiBold)
                }
            }
        }
    }
}

@Composable
private fun DashboardMetric(label: String, value: String, accent: androidx.compose.ui.graphics.Color, modifier: Modifier) {
    Column(modifier.padding(vertical = 1.dp), verticalArrangement = Arrangement.spacedBy(2.dp)) {
        Text(label, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(value, style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.Bold,
            color = accent, maxLines = 1)
    }
}

@Composable
private fun DashboardMiniCard(title: String, value: String, detail: String,
                              accent: androidx.compose.ui.graphics.Color, icon: androidx.compose.ui.graphics.vector.ImageVector) {
    InfoCard(title) {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            Icon(icon, null, tint = accent, modifier = Modifier.size(21.dp))
            Column(Modifier.weight(1f)) {
                Text(value, style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.Bold,
                    color = accent, maxLines = 1)
                Text(detail, style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant, maxLines = 2)
            }
        }
    }
}

@Composable
private fun RouterStatusHero(
    hostname: String, model: String, status: String,
    statusColor: androidx.compose.ui.graphics.Color, uptime: String
) {
    val shape = androidx.compose.foundation.shape.RoundedCornerShape(24.dp)
    Row(
        Modifier.fillMaxWidth()
            .background(
                androidx.compose.ui.graphics.Brush.linearGradient(
                    listOf(
                        androidx.compose.ui.graphics.Color(0xFF263F59),
                        androidx.compose.ui.graphics.Color(0xFF25334B),
                        androidx.compose.ui.graphics.Color(0xFF3C2E55)
                    )
                ), shape
            )
            .padding(horizontal = 16.dp, vertical = 14.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Surface(shape = androidx.compose.foundation.shape.RoundedCornerShape(16.dp),
            color = androidx.compose.ui.graphics.Color.White.copy(alpha = 0.12f),
            modifier = Modifier.size(46.dp)) {
            Box(contentAlignment = Alignment.Center) {
                Icon(painterResource(R.drawable.ic_routerdash_foreground), contentDescription = null,
                    tint = androidx.compose.ui.graphics.Color.Unspecified, modifier = Modifier.size(38.dp))
            }
        }
        Spacer(Modifier.width(12.dp))
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
            Text(hostname, style = MaterialTheme.typography.titleLarge,
                fontWeight = FontWeight.Bold, color = androidx.compose.ui.graphics.Color.White, maxLines = 1)
            Text(model, style = MaterialTheme.typography.labelMedium,
                color = androidx.compose.ui.graphics.Color.White.copy(alpha = 0.72f), maxLines = 1)
            Text("Маршрутизатор · OpenWrt", style = MaterialTheme.typography.labelSmall,
                color = androidx.compose.ui.graphics.Color.White.copy(alpha = 0.58f))
        }
        Column(horizontalAlignment = Alignment.End, verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Surface(shape = androidx.compose.foundation.shape.RoundedCornerShape(50),
                color = statusColor.copy(alpha = 0.18f)) {
                Row(Modifier.padding(horizontal = 9.dp, vertical = 5.dp),
                    verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(5.dp)) {
                    Box(Modifier.size(7.dp).background(statusColor,
                        androidx.compose.foundation.shape.CircleShape))
                    Text(status, color = statusColor, style = MaterialTheme.typography.labelSmall,
                        fontWeight = FontWeight.Bold, maxLines = 1)
                }
            }
            Text("Аптайм $uptime", style = MaterialTheme.typography.labelSmall,
                color = androidx.compose.ui.graphics.Color.White.copy(alpha = 0.72f))
        }
    }
}

@Composable
private fun CompactSystemMetric(label: String, value: String, modifier: Modifier = Modifier) {
    Column(modifier.padding(vertical = 3.dp), verticalArrangement = Arrangement.spacedBy(2.dp)) {
        Text(label, style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant, maxLines = 1)
        Text(value, style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.SemiBold,
            maxLines = 1)
    }
}

@Composable
private fun StatusRecommendationsCard(cpuPercent: Int?, ramPercent: Int?, availableRam: Long?) {
    val issues = buildList {
        if (cpuPercent != null && cpuPercent >= 85) add("Высокая загрузка CPU ($cpuPercent%). Проверь список процессов и активные службы.")
        if (ramPercent != null && ramPercent >= 90) add("Критически мало свободной памяти ($ramPercent% занято). Найди процессы с большим потреблением ОЗУ.")
        else if (ramPercent != null && ramPercent >= 80) add("ОЗУ занято на $ramPercent%. Проверь, не растёт ли потребление памяти со временем.")
        if (availableRam != null && availableRam < 64L * 1024L * 1024L)
            add("Свободно менее 64 МБ ОЗУ. Избегай запуска дополнительных тяжёлых служб.")
    }
    val warning = issues.isNotEmpty()
    InfoCard("Состояние системы и рекомендации") {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Icon(
                if (warning) Icons.Outlined.WarningAmber else Icons.Outlined.CheckCircle,
                contentDescription = null,
                tint = if (warning) MaterialTheme.colorScheme.tertiary else MaterialTheme.colorScheme.primary
            )
            Text(
                when {
                    cpuPercent == null || ramPercent == null -> "Собираем показатели для оценки"
                    warning -> "Требуется внимание"
                    else -> "Работает в нормальном режиме"
                },
                fontWeight = FontWeight.SemiBold
            )
        }
        if (issues.isEmpty()) {
            Text(
                if (cpuPercent == null || ramPercent == null) "Рекомендации появятся после получения статистики CPU и памяти."
                else "Критичных отклонений по загрузке процессора и памяти не обнаружено.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        } else {
            issues.forEach { recommendation ->
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.Top) {
                    Icon(Icons.Outlined.ChevronRight, contentDescription = null,
                        tint = MaterialTheme.colorScheme.tertiary, modifier = Modifier.size(18.dp))
                    Text(recommendation, style = MaterialTheme.typography.bodySmall)
                }
            }
        }
    }
}

@Composable
private fun CpuHistoryChart(history: List<Int>) {
    val accent = MaterialTheme.colorScheme.primary
    val grid = MaterialTheme.colorScheme.outline.copy(alpha = 0.22f)
    val label = MaterialTheme.colorScheme.onSurfaceVariant
    androidx.compose.foundation.Canvas(Modifier.fillMaxWidth().height(178.dp)) {
        val left = 34.dp.toPx()
        val right = 4.dp.toPx()
        val top = 8.dp.toPx()
        val bottom = 20.dp.toPx()
        val chartWidth = size.width - left - right
        val chartHeight = size.height - top - bottom
        listOf(0, 25, 50, 75, 100).forEach { tick ->
            val y = top + chartHeight * (1f - tick / 100f)
            drawLine(grid, androidx.compose.ui.geometry.Offset(left, y),
                androidx.compose.ui.geometry.Offset(size.width - right, y), 1.dp.toPx())
            // Grid tick; labels are omitted to keep the chart independent of Android Canvas APIs.
        }
        if (history.isEmpty()) return@Canvas
        val path = androidx.compose.ui.graphics.Path()
        val fill = androidx.compose.ui.graphics.Path()
        history.forEachIndexed { index, value ->
            val x = left + if (history.size == 1) chartWidth else chartWidth * index / (history.size - 1f)
            val y = top + chartHeight * (1f - value.coerceIn(0, 100) / 100f)
            if (index == 0) { path.moveTo(x, y); fill.moveTo(x, top + chartHeight); fill.lineTo(x, y) }
            else { path.lineTo(x, y); fill.lineTo(x, y) }
        }
        val lastX = left + if (history.size == 1) chartWidth else chartWidth
        fill.lineTo(lastX, top + chartHeight)
        fill.close()
        drawPath(fill, androidx.compose.ui.graphics.Brush.verticalGradient(
            listOf(accent.copy(alpha = 0.42f), accent.copy(alpha = 0.02f)),
            startY = top, endY = top + chartHeight))
        drawPath(path, accent, style = androidx.compose.ui.graphics.drawscope.Stroke(2.dp.toPx()))
    }
}

@Composable
private fun NetworkInformationCard(s: Snapshot) {
    val maxRate = maxOf(s.rxRate ?: 0L, s.txRate ?: 0L, 1024L)
    InfoCard("Скорость соединения · WAN") {
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            Speedometer("Приём", s.rxRate?.let { formatRate(it) } ?: "—",
                ((s.rxRate ?: 0L).toFloat() / maxRate).coerceIn(0f, 1f),
                androidx.compose.ui.graphics.Color(0xFF36D6C5), Modifier.weight(1f))
            Speedometer("Передача", s.txRate?.let { formatRate(it) } ?: "—",
                ((s.txRate ?: 0L).toFloat() / maxRate).coerceIn(0f, 1f),
                androidx.compose.ui.graphics.Color(0xFFFF9A52), Modifier.weight(1f))
        }
    }
}