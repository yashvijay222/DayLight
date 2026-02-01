/**
 * presage_daemon.cpp
 * SmartSpectra Vital Signs Daemon for DayLight Cognitive Load Tracker
 * 
 * This daemon receives video frames from the Python backend via TCP,
 * processes them through the Presage SmartSpectra SDK, and streams
 * metrics back via TCP.
 * 
 * Video Input: TCP port 9001 (receives JPEG frames from backend)
 * Metrics Output: TCP port 9002 (sends JSON metrics to backend)
 * 
 * Extended Metrics Output (Phase 2):
 * {
 *   "type": "metrics",
 *   "pulse_rate": 72.5,
 *   "pulse_confidence": 0.92,
 *   "pulse_trace": [[t1, v1], [t2, v2], ...],
 *   "breathing_rate": 15.2,
 *   "breathing_confidence": 0.88,
 *   "breathing_amplitude": [a1, a2, ...],
 *   "blinking": true,
 *   "talking": false,
 *   "apnea_detected": false
 * }
 */

#include <smartspectra/container/foreground_container.hpp>
#include <smartspectra/container/settings.hpp>
#include <physiology/modules/messages/metrics.h>
#include <physiology/modules/messages/status.h>
#include <absl/status/status.h>
#include <glog/logging.h>
#include <opencv2/opencv.hpp>
#include <nlohmann/json.hpp>

#include <string>
#include <thread>
#include <atomic>
#include <mutex>
#include <chrono>
#include <csignal>
#include <cstdlib>
#include <vector>
#include <set>
#include <memory>

// Networking
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <unistd.h>

using json = nlohmann::json;

// Global state for signal handling
std::atomic<bool> g_running{true};

// Configuration from environment
struct DaemonConfig {
    std::string api_key;
    int video_input_port = 9001;
    int metrics_output_port = 9002;
    int frame_width = 1280;
    int frame_height = 720;
    bool headless = true;
    int verbosity = 1;
    
    // Session recording configuration
    std::string recordings_dir = "/tmp/presage_recordings";
    int video_fps = 30;
};

void signal_handler(int signal) {
    LOG(INFO) << "Received signal " << signal << ", shutting down...";
    g_running = false;
}

DaemonConfig load_config() {
    DaemonConfig config;
    
    // API Key (required for full SDK)
    const char* api_key = std::getenv("SMARTSPECTRA_API_KEY");
    if (api_key) {
        config.api_key = api_key;
    } else {
        LOG(WARNING) << "SMARTSPECTRA_API_KEY not set - using demo mode";
        config.api_key = "";
    }
    
    // Video input port
    const char* video_port = std::getenv("VIDEO_INPUT_PORT");
    if (video_port) {
        config.video_input_port = std::stoi(video_port);
    }
    
    // Metrics output port
    const char* metrics_port = std::getenv("METRICS_OUTPUT_PORT");
    if (metrics_port) {
        config.metrics_output_port = std::stoi(metrics_port);
    }
    
    // Headless mode
    const char* headless = std::getenv("HEADLESS");
    if (headless) {
        config.headless = (std::string(headless) == "true" || std::string(headless) == "1");
    }
    
    // Verbosity level
    const char* verbosity = std::getenv("VERBOSITY");
    if (verbosity) {
        config.verbosity = std::stoi(verbosity);
    }
    
    // Recordings directory
    const char* recordings_dir = std::getenv("PRESAGE_RECORDINGS_DIR");
    if (recordings_dir) {
        config.recordings_dir = recordings_dir;
    }
    
    // Video FPS for recording
    const char* video_fps = std::getenv("PRESAGE_VIDEO_FPS");
    if (video_fps) {
        config.video_fps = std::stoi(video_fps);
    }
    
    return config;
}

// Convert status to JSON string
std::string status_to_json(const std::string& status, const std::string& message) {
    json j;
    j["type"] = "status";
    j["status"] = status;
    j["message"] = message;
    j["timestamp"] = std::chrono::duration_cast<std::chrono::milliseconds>(
        std::chrono::system_clock::now().time_since_epoch()).count();
    
    return j.dump();
}

// ============================================================================
// Session Recorder - Records video frames to disk for SDK processing
// ============================================================================

class SessionRecorder {
public:
    SessionRecorder(const std::string& recordings_dir, int default_fps = 30)
        : recordings_dir_(recordings_dir), default_fps_(default_fps), recording_(false) {
        // Create recordings directory if it doesn't exist
        createDirectory(recordings_dir_);
    }
    
    ~SessionRecorder() {
        stopRecording();
    }
    
    /**
     * Start a new recording session.
     * 
     * @param session_id Unique session identifier (used in filename)
     * @param fps Frame rate for the video (default: 30)
     * @param width Frame width (0 = auto-detect from first frame)
     * @param height Frame height (0 = auto-detect from first frame)
     * @return true if session started successfully
     */
    bool startSession(const std::string& session_id, int fps = 0, int width = 0, int height = 0) {
        std::lock_guard<std::mutex> lock(mutex_);
        
        if (recording_) {
            LOG(WARNING) << "Recording already in progress for session " << current_session_id_;
            return false;
        }
        
        current_session_id_ = session_id;
        session_fps_ = (fps > 0) ? fps : default_fps_;
        session_width_ = width;
        session_height_ = height;
        
        // Generate output filename with timestamp
        auto now = std::chrono::system_clock::now();
        auto timestamp = std::chrono::duration_cast<std::chrono::seconds>(now.time_since_epoch()).count();
        
        current_video_path_ = recordings_dir_ + "/" + session_id + "_" + std::to_string(timestamp) + ".avi";
        
        // If dimensions are provided, initialize writer immediately
        if (width > 0 && height > 0) {
            if (!initializeWriter(width, height)) {
                return false;
            }
        }
        // Otherwise, writer will be initialized on first frame
        
        recording_ = true;
        frame_count_ = 0;
        
        LOG(INFO) << "Started recording session " << session_id 
                  << " at " << session_fps_ << " fps"
                  << " -> " << current_video_path_;
        
        return true;
    }
    
    /**
     * Add a frame to the current recording.
     * If no session is active, this is a no-op.
     * 
     * @param frame The frame to record (BGR format)
     * @return true if frame was recorded successfully
     */
    bool addFrame(const cv::Mat& frame) {
        std::lock_guard<std::mutex> lock(mutex_);
        
        if (!recording_) {
            return false;
        }
        
        if (frame.empty()) {
            LOG(WARNING) << "Attempted to record empty frame";
            return false;
        }
        
        // Initialize writer on first frame if dimensions weren't specified
        if (!writer_.isOpened()) {
            if (!initializeWriter(frame.cols, frame.rows)) {
                recording_ = false;
                return false;
            }
        }
        
        // Resize frame if it doesn't match expected dimensions
        cv::Mat frame_to_write;
        if (frame.cols != session_width_ || frame.rows != session_height_) {
            cv::resize(frame, frame_to_write, cv::Size(session_width_, session_height_));
        } else {
            frame_to_write = frame;
        }
        
        writer_.write(frame_to_write);
        frame_count_++;
        
        return true;
    }
    
    /**
     * Stop the current recording session.
     * 
     * @return Path to the recorded video file, or empty string if no recording was active
     */
    std::string stopRecording() {
        std::lock_guard<std::mutex> lock(mutex_);
        
        if (!recording_) {
            return "";
        }
        
        recording_ = false;
        
        if (writer_.isOpened()) {
            writer_.release();
        }
        
        std::string video_path = current_video_path_;
        
        LOG(INFO) << "Stopped recording session " << current_session_id_ 
                  << " - " << frame_count_ << " frames"
                  << " -> " << video_path;
        
        // Reset state
        current_session_id_.clear();
        current_video_path_.clear();
        frame_count_ = 0;
        
        return video_path;
    }
    
    /**
     * Check if a recording is currently active.
     */
    bool isRecording() const {
        std::lock_guard<std::mutex> lock(mutex_);
        return recording_;
    }
    
    /**
     * Get the current session ID.
     */
    std::string getCurrentSessionId() const {
        std::lock_guard<std::mutex> lock(mutex_);
        return current_session_id_;
    }
    
    /**
     * Get the current video file path.
     */
    std::string getCurrentVideoPath() const {
        std::lock_guard<std::mutex> lock(mutex_);
        return current_video_path_;
    }
    
    /**
     * Get the number of frames recorded in the current session.
     */
    size_t getFrameCount() const {
        std::lock_guard<std::mutex> lock(mutex_);
        return frame_count_;
    }
    
    /**
     * Get the recordings directory path.
     */
    std::string getRecordingsDir() const {
        return recordings_dir_;
    }
    
private:
    bool initializeWriter(int width, int height) {
        session_width_ = width;
        session_height_ = height;
        
        // Use MJPG codec for good compatibility and quality
        int fourcc = cv::VideoWriter::fourcc('M', 'J', 'P', 'G');
        
        writer_.open(current_video_path_, fourcc, session_fps_, 
                     cv::Size(session_width_, session_height_), true);
        
        if (!writer_.isOpened()) {
            LOG(ERROR) << "Failed to open VideoWriter for " << current_video_path_;
            return false;
        }
        
        LOG(INFO) << "Initialized VideoWriter: " << session_width_ << "x" << session_height_ 
                  << " @ " << session_fps_ << " fps (MJPG)";
        
        return true;
    }
    
    bool createDirectory(const std::string& path) {
        // Simple directory creation using system call
        std::string cmd = "mkdir -p \"" + path + "\"";
        int result = system(cmd.c_str());
        if (result != 0) {
            LOG(WARNING) << "Could not create directory: " << path;
            return false;
        }
        LOG(INFO) << "Ensured recordings directory exists: " << path;
        return true;
    }
    
    std::string recordings_dir_;
    int default_fps_;
    
    mutable std::mutex mutex_;
    bool recording_;
    std::string current_session_id_;
    std::string current_video_path_;
    int session_fps_;
    int session_width_;
    int session_height_;
    size_t frame_count_;
    
    cv::VideoWriter writer_;
};

// Global session recorder (initialized in main)
std::unique_ptr<SessionRecorder> g_session_recorder;

// Forward declarations
class MetricsServer;
class SDKVideoProcessor;

// Global pointers (initialized in main)
MetricsServer* g_metrics_server = nullptr;
std::unique_ptr<SDKVideoProcessor> g_sdk_processor;

// TCP Server for metrics output
class MetricsServer {
public:
    MetricsServer(int port) : port_(port), server_fd_(-1), running_(false) {}
    
    ~MetricsServer() {
        stop();
    }
    
    bool start() {
        server_fd_ = socket(AF_INET, SOCK_STREAM, 0);
        if (server_fd_ < 0) {
            LOG(ERROR) << "Failed to create metrics socket";
            return false;
        }
        
        int opt = 1;
        setsockopt(server_fd_, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt));
        
        struct sockaddr_in address;
        address.sin_family = AF_INET;
        address.sin_addr.s_addr = INADDR_ANY;
        address.sin_port = htons(port_);
        
        if (bind(server_fd_, (struct sockaddr*)&address, sizeof(address)) < 0) {
            LOG(ERROR) << "Failed to bind metrics server to port " << port_;
            close(server_fd_);
            return false;
        }
        
        if (listen(server_fd_, 5) < 0) {
            LOG(ERROR) << "Failed to listen on metrics socket";
            close(server_fd_);
            return false;
        }
        
        running_ = true;
        server_thread_ = std::thread(&MetricsServer::acceptLoop, this);
        
        LOG(INFO) << "Metrics server listening on port " << port_;
        return true;
    }
    
    void stop() {
        running_ = false;
        if (server_fd_ >= 0) {
            shutdown(server_fd_, SHUT_RDWR);
            close(server_fd_);
            server_fd_ = -1;
        }
        if (server_thread_.joinable()) {
            server_thread_.join();
        }
        
        std::lock_guard<std::mutex> lock(clients_mutex_);
        for (int fd : client_fds_) {
            close(fd);
        }
        client_fds_.clear();
    }
    
    void broadcast(const std::string& message) {
        std::lock_guard<std::mutex> lock(clients_mutex_);
        std::vector<int> disconnected;
        
        std::string msg_with_newline = message + "\n";
        
        for (int fd : client_fds_) {
            ssize_t sent = send(fd, msg_with_newline.c_str(), msg_with_newline.size(), MSG_NOSIGNAL);
            if (sent < 0) {
                disconnected.push_back(fd);
            }
        }
        
        for (int fd : disconnected) {
            close(fd);
            client_fds_.erase(fd);
            LOG(INFO) << "Metrics client disconnected";
        }
    }
    
    bool hasClients() {
        std::lock_guard<std::mutex> lock(clients_mutex_);
        return !client_fds_.empty();
    }
    
private:
    void acceptLoop() {
        while (running_ && g_running) {
            fd_set readfds;
            FD_ZERO(&readfds);
            FD_SET(server_fd_, &readfds);
            
            struct timeval tv;
            tv.tv_sec = 1;
            tv.tv_usec = 0;
            
            int activity = select(server_fd_ + 1, &readfds, NULL, NULL, &tv);
            
            if (activity < 0 && errno != EINTR) {
                continue;
            }
            
            if (activity > 0 && FD_ISSET(server_fd_, &readfds)) {
                struct sockaddr_in client_addr;
                socklen_t client_len = sizeof(client_addr);
                int client_fd = accept(server_fd_, (struct sockaddr*)&client_addr, &client_len);
                
                if (client_fd >= 0) {
                    std::lock_guard<std::mutex> lock(clients_mutex_);
                    client_fds_.insert(client_fd);
                    LOG(INFO) << "Metrics client connected from " << inet_ntoa(client_addr.sin_addr);
                }
            }
        }
    }
    
    int port_;
    int server_fd_;
    std::atomic<bool> running_;
    std::thread server_thread_;
    std::mutex clients_mutex_;
    std::set<int> client_fds_;
};

// ============================================================================
// SDK Video Processor - Processes recorded video files with SmartSpectra SDK
// ============================================================================

using namespace presage::smartspectra;

/**
 * SDKVideoProcessor runs the SmartSpectra SDK on recorded video files
 * and broadcasts the resulting metrics via the MetricsServer.
 * 
 * Processing happens in a background thread so it doesn't block
 * the video input server from accepting new sessions.
 */
class SDKVideoProcessor {
public:
    SDKVideoProcessor(const std::string& api_key, int frame_width, int frame_height)
        : api_key_(api_key), frame_width_(frame_width), frame_height_(frame_height),
          processing_(false) {}
    
    ~SDKVideoProcessor() {
        waitForCompletion();
    }
    
    /**
     * Process a recorded video file using the SmartSpectra SDK.
     * Runs in a background thread.
     * 
     * @param video_path Path to the recorded video file
     * @param session_id Session identifier for logging
     * @return true if processing was started, false if already processing
     */
    bool processVideoAsync(const std::string& video_path, const std::string& session_id) {
        // Check if already processing
        if (processing_.load()) {
            LOG(WARNING) << "SDK already processing another video";
            return false;
        }
        
        // Wait for any previous processing thread to complete
        waitForCompletion();
        
        // Start new processing thread
        processing_ = true;
        current_session_id_ = session_id;
        
        processing_thread_ = std::thread(&SDKVideoProcessor::processVideo, this, 
                                         video_path, session_id);
        
        LOG(INFO) << "Started SDK processing for session " << session_id 
                  << " in background thread";
        return true;
    }
    
    /**
     * Check if SDK processing is currently in progress.
     */
    bool isProcessing() const {
        return processing_.load();
    }
    
    /**
     * Get the current session being processed.
     */
    std::string getCurrentSessionId() const {
        return current_session_id_;
    }
    
    /**
     * Wait for the current processing to complete.
     */
    void waitForCompletion() {
        if (processing_thread_.joinable()) {
            processing_thread_.join();
        }
    }
    
private:
    void processVideo(const std::string& video_path, const std::string& session_id) {
        LOG(INFO) << "SDK processing started for: " << video_path;
        
        // Broadcast processing start status
        if (g_metrics_server) {
            json status_msg;
            status_msg["type"] = "sdk_status";
            status_msg["status"] = "processing_started";
            status_msg["session_id"] = session_id;
            status_msg["video_path"] = video_path;
            status_msg["timestamp"] = std::chrono::duration_cast<std::chrono::milliseconds>(
                std::chrono::system_clock::now().time_since_epoch()).count();
            g_metrics_server->broadcast(status_msg.dump());
        }
        
        try {
            // Create SDK settings
            container::settings::Settings<
                container::settings::OperationMode::Continuous,
                container::settings::IntegrationMode::Rest
            > settings;
            
            // Configure video source for file input
            settings.video_source.input_video_path = video_path;
            settings.video_source.device_index = -1;  // Disable camera, use file
            settings.video_source.capture_width_px = frame_width_;
            settings.video_source.capture_height_px = frame_height_;
            settings.video_source.codec = presage::camera::CaptureCodec::MJPG;
            settings.video_source.auto_lock = true;
            
            // SDK configuration
            settings.headless = true;  // No GUI
            settings.enable_edge_metrics = true;
            settings.verbosity_level = 1;
            settings.continuous.preprocessed_data_buffer_duration_s = 0.5;
            settings.integration.api_key = api_key_;
            
            // Create SDK container
            auto container = std::make_unique<container::CpuContinuousRestForegroundContainer>(settings);
            
            // Track metrics count for this session
            size_t metrics_count = 0;
            
            // Register metrics callback
            auto metrics_status = container->SetOnCoreMetricsOutput(
                [this, session_id, &metrics_count](const presage::physiology::MetricsBuffer& metrics, int64_t timestamp) {
                    // Convert SDK metrics to our JSON format and broadcast
                    std::string json_str = sdkMetricsToJson(metrics, timestamp, session_id);
                    
                    if (g_metrics_server) {
                        g_metrics_server->broadcast(json_str);
                    }
                    
                    metrics_count++;
                    
                    // Log periodically
                    if (metrics_count % 10 == 0) {
                        LOG(INFO) << "SDK metrics broadcast #" << metrics_count 
                                  << " for session " << session_id;
                    }
                    
                    return absl::OkStatus();
                }
            );
            
            if (!metrics_status.ok()) {
                LOG(ERROR) << "Failed to set SDK metrics callback: " << metrics_status.message();
                broadcastError(session_id, "Failed to set metrics callback");
                processing_ = false;
                return;
            }
            
            // Register status callback
            container->SetOnStatusChange(
                [this, session_id](presage::physiology::StatusValue imaging_status) {
                    std::string status_desc = presage::physiology::GetStatusDescription(imaging_status.value());
                    LOG(INFO) << "SDK Status [" << session_id << "]: " << status_desc;
                    
                    // Broadcast status changes
                    if (g_metrics_server) {
                        json status_msg;
                        status_msg["type"] = "sdk_imaging_status";
                        status_msg["session_id"] = session_id;
                        status_msg["status"] = status_desc;
                        status_msg["status_code"] = static_cast<int>(imaging_status.value());
                        status_msg["timestamp"] = std::chrono::duration_cast<std::chrono::milliseconds>(
                            std::chrono::system_clock::now().time_since_epoch()).count();
                        g_metrics_server->broadcast(status_msg.dump());
                    }
                    
                    return absl::OkStatus();
                }
            );
            
            // Initialize SDK
            LOG(INFO) << "Initializing SDK for video: " << video_path;
            if (auto init_status = container->Initialize(); !init_status.ok()) {
                LOG(ERROR) << "Failed to initialize SDK: " << init_status.message();
                broadcastError(session_id, "SDK initialization failed: " + std::string(init_status.message()));
                processing_ = false;
                return;
            }
            
            LOG(INFO) << "SDK initialized, starting video processing...";
            
            // Run processing (blocks until video ends)
            if (auto run_status = container->Run(); !run_status.ok()) {
                // CancelledError is normal when video ends
                if (!absl::IsCancelled(run_status)) {
                    LOG(ERROR) << "SDK processing error: " << run_status.message();
                    broadcastError(session_id, "SDK processing error: " + std::string(run_status.message()));
                }
            }
            
            LOG(INFO) << "SDK processing completed for session " << session_id 
                      << " - " << metrics_count << " metrics generated";
            
            // Broadcast completion status
            if (g_metrics_server) {
                json status_msg;
                status_msg["type"] = "sdk_status";
                status_msg["status"] = "processing_completed";
                status_msg["session_id"] = session_id;
                status_msg["metrics_count"] = metrics_count;
                status_msg["timestamp"] = std::chrono::duration_cast<std::chrono::milliseconds>(
                    std::chrono::system_clock::now().time_since_epoch()).count();
                g_metrics_server->broadcast(status_msg.dump());
            }
            
        } catch (const std::exception& e) {
            LOG(ERROR) << "SDK processing exception: " << e.what();
            broadcastError(session_id, std::string("SDK exception: ") + e.what());
        }
        
        processing_ = false;
        current_session_id_.clear();
    }
    
    /**
     * Convert SDK MetricsBuffer to our extended JSON format.
     */
    std::string sdkMetricsToJson(const presage::physiology::MetricsBuffer& metrics, 
                                  int64_t timestamp, const std::string& session_id) {
        json j;
        j["type"] = "metrics";
        j["source"] = "presage_sdk";
        j["session_id"] = session_id;
        j["timestamp"] = timestamp;
        
        // =====================================================================
        // PULSE METRICS
        // =====================================================================
        
        // Extract pulse rate from the most recent rate measurement
        float pulse_rate = 0.0f;
        float pulse_confidence = 0.0f;
        if (metrics.pulse().rate_size() > 0) {
            // Get the last (most recent) rate measurement
            const auto& last_rate = metrics.pulse().rate(metrics.pulse().rate_size() - 1);
            pulse_rate = last_rate.value();
            pulse_confidence = last_rate.confidence();
        } else if (metrics.has_pulse() && metrics.pulse().has_strict()) {
            // Fallback to strict value if rate array is empty
            pulse_rate = metrics.pulse().strict().value();
        }
        j["pulse_rate"] = pulse_rate;
        j["pulse_confidence"] = pulse_confidence;
        
        // Extract full pulse trace for HRV calculation (PPG signal)
        // Format: [[time1, value1], [time2, value2], ...]
        json trace_array = json::array();
        for (int i = 0; i < metrics.pulse().trace_size(); ++i) {
            const auto& trace_point = metrics.pulse().trace(i);
            trace_array.push_back({trace_point.time(), trace_point.value()});
        }
        j["pulse_trace"] = trace_array;
        
        // =====================================================================
        // BREATHING METRICS
        // =====================================================================
        
        // Extract breathing rate from the most recent rate measurement
        float breathing_rate = 0.0f;
        float breathing_confidence = 0.0f;
        if (metrics.breathing().rate_size() > 0) {
            // Get the last (most recent) rate measurement
            const auto& last_rate = metrics.breathing().rate(metrics.breathing().rate_size() - 1);
            breathing_rate = last_rate.value();
            breathing_confidence = last_rate.confidence();
        } else if (metrics.has_breathing() && metrics.breathing().has_strict()) {
            // Fallback to strict value if rate array is empty
            breathing_rate = metrics.breathing().strict().value();
        }
        j["breathing_rate"] = breathing_rate;
        j["breathing_confidence"] = breathing_confidence;
        
        // Extract breathing amplitude (depth of breathing over time)
        // Format: [[time1, value1], [time2, value2], ...]
        json amplitude_array = json::array();
        for (int i = 0; i < metrics.breathing().amplitude_size(); ++i) {
            const auto& amp_point = metrics.breathing().amplitude(i);
            amplitude_array.push_back({amp_point.time(), amp_point.value()});
        }
        j["breathing_amplitude"] = amplitude_array;
        
        // Extract upper breathing trace (chest movement signal)
        json upper_trace_array = json::array();
        for (int i = 0; i < metrics.breathing().upper_trace_size(); ++i) {
            const auto& trace_point = metrics.breathing().upper_trace(i);
            upper_trace_array.push_back({trace_point.time(), trace_point.value()});
        }
        j["breathing_upper_trace"] = upper_trace_array;
        
        // =====================================================================
        // APNEA DETECTION
        // =====================================================================
        
        // Check if apnea was detected in the most recent apnea event
        bool apnea_detected = false;
        if (metrics.breathing().apnea_size() > 0) {
            // Get the most recent apnea event
            const auto& last_apnea = metrics.breathing().apnea(metrics.breathing().apnea_size() - 1);
            apnea_detected = last_apnea.detected();
        }
        j["apnea_detected"] = apnea_detected;
        
        // =====================================================================
        // FACE METRICS
        // =====================================================================
        
        // Check if blinking was detected in the most recent blinking event
        bool blinking = false;
        if (metrics.face().blinking_size() > 0) {
            // Get the most recent blink event
            const auto& last_blink = metrics.face().blinking(metrics.face().blinking_size() - 1);
            blinking = last_blink.detected();
        }
        j["blinking"] = blinking;
        
        // Check if talking was detected in the most recent talking event
        bool talking = false;
        if (metrics.face().talking_size() > 0) {
            // Get the most recent talking event
            const auto& last_talk = metrics.face().talking(metrics.face().talking_size() - 1);
            talking = last_talk.detected();
        }
        j["talking"] = talking;
        
        // =====================================================================
        // ADDITIONAL METADATA
        // =====================================================================
        
        // Include measurement metadata if available
        if (metrics.has_metadata()) {
            j["measurement_id"] = metrics.metadata().id();
            j["upload_timestamp"] = metrics.metadata().upload_timestamp();
        }
        
        // =====================================================================
        // BLOOD PRESSURE (if enabled and available)
        // =====================================================================
        
        // Note: Blood pressure requires enable_phasic_bp = true in settings
        if (metrics.has_blood_pressure() && metrics.blood_pressure().phasic_size() > 0) {
            const auto& last_bp = metrics.blood_pressure().phasic(metrics.blood_pressure().phasic_size() - 1);
            j["phasic_blood_pressure"] = last_bp.value();
        }
        
        return j.dump();
    }
    
    void broadcastError(const std::string& session_id, const std::string& error) {
        if (g_metrics_server) {
            json error_msg;
            error_msg["type"] = "sdk_status";
            error_msg["status"] = "error";
            error_msg["session_id"] = session_id;
            error_msg["error"] = error;
            error_msg["timestamp"] = std::chrono::duration_cast<std::chrono::milliseconds>(
                std::chrono::system_clock::now().time_since_epoch()).count();
            g_metrics_server->broadcast(error_msg.dump());
        }
    }
    
    std::string api_key_;
    int frame_width_;
    int frame_height_;
    
    std::atomic<bool> processing_;
    std::string current_session_id_;
    std::thread processing_thread_;
};

// TCP Server for video input
class VideoInputServer {
public:
    VideoInputServer(int port) : port_(port), server_fd_(-1), running_(false) {}
    
    ~VideoInputServer() {
        stop();
    }
    
    bool start() {
        server_fd_ = socket(AF_INET, SOCK_STREAM, 0);
        if (server_fd_ < 0) {
            LOG(ERROR) << "Failed to create video input socket";
            return false;
        }
        
        int opt = 1;
        setsockopt(server_fd_, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt));
        
        struct sockaddr_in address;
        address.sin_family = AF_INET;
        address.sin_addr.s_addr = INADDR_ANY;
        address.sin_port = htons(port_);
        
        if (bind(server_fd_, (struct sockaddr*)&address, sizeof(address)) < 0) {
            LOG(ERROR) << "Failed to bind video server to port " << port_;
            close(server_fd_);
            return false;
        }
        
        if (listen(server_fd_, 1) < 0) {
            LOG(ERROR) << "Failed to listen on video socket";
            close(server_fd_);
            return false;
        }
        
        running_ = true;
        server_thread_ = std::thread(&VideoInputServer::acceptAndReceive, this);
        
        LOG(INFO) << "Video input server listening on port " << port_;
        return true;
    }
    
    void stop() {
        running_ = false;
        if (server_fd_ >= 0) {
            shutdown(server_fd_, SHUT_RDWR);
            close(server_fd_);
            server_fd_ = -1;
        }
        if (server_thread_.joinable()) {
            server_thread_.join();
        }
    }
    
private:
    void acceptAndReceive() {
        while (running_ && g_running) {
            fd_set readfds;
            FD_ZERO(&readfds);
            FD_SET(server_fd_, &readfds);
            
            struct timeval tv;
            tv.tv_sec = 1;
            tv.tv_usec = 0;
            
            int activity = select(server_fd_ + 1, &readfds, NULL, NULL, &tv);
            
            if (activity < 0 && errno != EINTR) {
                continue;
            }
            
            if (activity > 0 && FD_ISSET(server_fd_, &readfds)) {
                struct sockaddr_in client_addr;
                socklen_t client_len = sizeof(client_addr);
                int client_fd = accept(server_fd_, (struct sockaddr*)&client_addr, &client_len);
                
                if (client_fd >= 0) {
                    LOG(INFO) << "Video client connected from " << inet_ntoa(client_addr.sin_addr);
                    handleVideoClient(client_fd);
                    close(client_fd);
                    LOG(INFO) << "Video client disconnected";
                }
            }
        }
    }
    
    void handleVideoClient(int client_fd) {
        std::vector<uint8_t> buffer;
        uint8_t header[4];
        
        while (running_ && g_running) {
            // Read 4-byte frame length header
            ssize_t received = recv(client_fd, header, 4, MSG_WAITALL);
            if (received != 4) {
                break;
            }
            
            // Parse frame length (big-endian)
            uint32_t frame_length = (header[0] << 24) | (header[1] << 16) | 
                                    (header[2] << 8) | header[3];
            
            if (frame_length > 10 * 1024 * 1024) {  // Max 10MB per frame
                LOG(WARNING) << "Frame too large: " << frame_length;
                break;
            }
            
            // Read payload data
            buffer.resize(frame_length);
            received = recv(client_fd, buffer.data(), frame_length, MSG_WAITALL);
            if (received != static_cast<ssize_t>(frame_length)) {
                break;
            }
            
            // Check if payload is a JSON control message (starts with '{')
            if (frame_length > 0 && buffer[0] == '{') {
                // Parse and handle control message
                std::string json_str(buffer.begin(), buffer.end());
                handleControlMessage(json_str, client_fd);
                continue;
            }
            
            // Otherwise, decode as JPEG frame
            cv::Mat frame = cv::imdecode(buffer, cv::IMREAD_COLOR);
            if (frame.empty()) {
                LOG(WARNING) << "Failed to decode frame";
                continue;
            }
            
            // Record frame to session video file (if session is active)
            if (g_session_recorder) {
                g_session_recorder->addFrame(frame);
            }
            
        }
        
        // If session was active when client disconnected, stop recording and trigger SDK
        if (g_session_recorder && g_session_recorder->isRecording()) {
            std::string session_id = g_session_recorder->getCurrentSessionId();
            size_t frame_count = g_session_recorder->getFrameCount();
            std::string video_path = g_session_recorder->stopRecording();
            
            LOG(INFO) << "Video client disconnected - stopped recording: " << video_path 
                      << " (" << frame_count << " frames)";
            
            // Trigger SDK processing for the incomplete session
            if (g_sdk_processor && frame_count > 0) {
                bool started = g_sdk_processor->processVideoAsync(video_path, session_id);
                if (started) {
                    LOG(INFO) << "Started SDK processing for interrupted session " << session_id;
                } else {
                    LOG(WARNING) << "Could not start SDK processing - processor busy";
                }
            }
        }
    }
    
    /**
     * Handle a JSON control message from the video client.
     * 
     * Supported messages:
     * - {"type":"session_start","session_id":"...","fps":30,"width":1280,"height":720}
     * - {"type":"session_end","session_id":"..."}
     */
    void handleControlMessage(const std::string& json_str, int client_fd) {
        try {
            json msg = json::parse(json_str);
            std::string msg_type = msg.value("type", "");
            
            if (msg_type == "session_start") {
                handleSessionStart(msg, client_fd);
            } else if (msg_type == "session_end") {
                handleSessionEnd(msg, client_fd);
            } else {
                LOG(WARNING) << "Unknown control message type: " << msg_type;
                sendControlResponse(client_fd, "error", "Unknown message type: " + msg_type);
            }
        } catch (const json::parse_error& e) {
            LOG(ERROR) << "Failed to parse control message: " << e.what();
            sendControlResponse(client_fd, "error", "Invalid JSON: " + std::string(e.what()));
        } catch (const std::exception& e) {
            LOG(ERROR) << "Error handling control message: " << e.what();
            sendControlResponse(client_fd, "error", std::string(e.what()));
        }
    }
    
    /**
     * Handle session_start control message.
     * Starts recording video frames to a file.
     */
    void handleSessionStart(const json& msg, int client_fd) {
        if (!g_session_recorder) {
            sendControlResponse(client_fd, "error", "Session recorder not initialized");
            return;
        }
        
        // Extract parameters
        std::string session_id = msg.value("session_id", "");
        if (session_id.empty()) {
            // Generate a session ID if not provided
            auto now = std::chrono::system_clock::now();
            auto timestamp = std::chrono::duration_cast<std::chrono::milliseconds>(
                now.time_since_epoch()).count();
            session_id = "session_" + std::to_string(timestamp);
        }
        
        int fps = msg.value("fps", 0);
        int width = msg.value("width", 0);
        int height = msg.value("height", 0);
        
        // Check if already recording
        if (g_session_recorder->isRecording()) {
            std::string current_id = g_session_recorder->getCurrentSessionId();
            LOG(WARNING) << "Session already in progress: " << current_id;
            sendControlResponse(client_fd, "error", 
                "Session already in progress: " + current_id);
            return;
        }
        
        // Start recording
        if (g_session_recorder->startSession(session_id, fps, width, height)) {
            LOG(INFO) << "Started session: " << session_id 
                      << " (fps=" << fps << ", " << width << "x" << height << ")";
            
            json response;
            response["type"] = "session_started";
            response["session_id"] = session_id;
            response["video_path"] = g_session_recorder->getCurrentVideoPath();
            sendControlResponse(client_fd, response);
        } else {
            sendControlResponse(client_fd, "error", "Failed to start session");
        }
    }
    
    /**
     * Handle session_end control message.
     * Stops recording and returns the video file path.
     */
    void handleSessionEnd(const json& msg, int client_fd) {
        if (!g_session_recorder) {
            sendControlResponse(client_fd, "error", "Session recorder not initialized");
            return;
        }
        
        std::string session_id = msg.value("session_id", "");
        
        // Check if recording
        if (!g_session_recorder->isRecording()) {
            LOG(WARNING) << "No session in progress";
            sendControlResponse(client_fd, "error", "No session in progress");
            return;
        }
        
        // Verify session ID if provided
        std::string current_id = g_session_recorder->getCurrentSessionId();
        if (!session_id.empty() && session_id != current_id) {
            LOG(WARNING) << "Session ID mismatch: expected " << current_id 
                         << ", got " << session_id;
            sendControlResponse(client_fd, "error", 
                "Session ID mismatch: expected " + current_id);
            return;
        }
        
        // Stop recording
        size_t frame_count = g_session_recorder->getFrameCount();
        std::string video_path = g_session_recorder->stopRecording();
        
        LOG(INFO) << "Ended session: " << current_id 
                  << " (" << frame_count << " frames) -> " << video_path;
        
        json response;
        response["type"] = "session_ended";
        response["session_id"] = current_id;
        response["video_path"] = video_path;
        response["frame_count"] = frame_count;
        
        // Trigger SDK processing in background thread
        bool sdk_started = false;
        if (g_sdk_processor && frame_count > 0) {
            sdk_started = g_sdk_processor->processVideoAsync(video_path, current_id);
            response["sdk_processing"] = sdk_started ? "started" : "busy";
            
            if (!sdk_started) {
                LOG(WARNING) << "Could not start SDK processing - processor busy";
            }
        } else if (frame_count == 0) {
            response["sdk_processing"] = "skipped";
            LOG(INFO) << "Skipping SDK processing - no frames recorded";
        } else {
            response["sdk_processing"] = "unavailable";
            LOG(WARNING) << "SDK processor not initialized";
        }
        
        sendControlResponse(client_fd, response);
    }
    
    /**
     * Send a control response back to the client.
     */
    void sendControlResponse(int client_fd, const std::string& status, const std::string& message) {
        json response;
        response["type"] = "control_response";
        response["status"] = status;
        response["message"] = message;
        response["timestamp"] = std::chrono::duration_cast<std::chrono::milliseconds>(
            std::chrono::system_clock::now().time_since_epoch()).count();
        sendControlResponse(client_fd, response);
    }
    
    void sendControlResponse(int client_fd, const json& response) {
        std::string json_str = response.dump();
        
        // Send with same protocol: 4-byte length header + payload
        uint32_t length = static_cast<uint32_t>(json_str.size());
        uint8_t header[4];
        header[0] = (length >> 24) & 0xFF;
        header[1] = (length >> 16) & 0xFF;
        header[2] = (length >> 8) & 0xFF;
        header[3] = length & 0xFF;
        
        send(client_fd, header, 4, MSG_NOSIGNAL);
        send(client_fd, json_str.c_str(), json_str.size(), MSG_NOSIGNAL);
    }
    
    int port_;
    int server_fd_;
    std::atomic<bool> running_;
    std::thread server_thread_;
};

int main(int argc, char** argv) {
    // Initialize logging
    google::InitGoogleLogging(argv[0]);
    FLAGS_alsologtostderr = true;
    
    // Set up signal handlers
    std::signal(SIGINT, signal_handler);
    std::signal(SIGTERM, signal_handler);
    
    LOG(INFO) << "Starting Presage Daemon for DayLight (Phase 2 - Extended Metrics)...";
    
    // Load configuration
    DaemonConfig config = load_config();
    LOG(INFO) << "Configuration:";
    LOG(INFO) << "  Video input port: " << config.video_input_port;
    LOG(INFO) << "  Metrics output port: " << config.metrics_output_port;
    LOG(INFO) << "  Headless mode: " << (config.headless ? "true" : "false");
    LOG(INFO) << "  Recordings dir: " << config.recordings_dir;
    LOG(INFO) << "  Video FPS: " << config.video_fps;
    
    // Initialize session recorder
    g_session_recorder = std::make_unique<SessionRecorder>(config.recordings_dir, config.video_fps);
    LOG(INFO) << "Session recorder initialized - recordings will be saved to " << config.recordings_dir;
    
    // Start servers
    MetricsServer metrics_server(config.metrics_output_port);
    if (!metrics_server.start()) {
        LOG(FATAL) << "Failed to start metrics server";
        return 1;
    }
    
    // Set global metrics server pointer for SDK processor callbacks
    g_metrics_server = &metrics_server;
    
    // Initialize SDK video processor
    g_sdk_processor = std::make_unique<SDKVideoProcessor>(
        config.api_key, config.frame_width, config.frame_height);
    LOG(INFO) << "SDK video processor initialized";
    if (config.api_key.empty()) {
        LOG(WARNING) << "No API key configured - SDK processing may be limited";
    }
    
    VideoInputServer video_server(config.video_input_port);
    if (!video_server.start()) {
        LOG(FATAL) << "Failed to start video input server";
        return 1;
    }
    
    // Send startup notification
    metrics_server.broadcast(status_to_json("ready", "Presage daemon started (SDK integration)"));
    
    LOG(INFO) << "Daemon ready. Waiting for session recordings on port " << config.video_input_port;
    LOG(INFO) << "SDK metrics will be sent on port " << config.metrics_output_port;
    
    // Idle loop: video ingestion and SDK processing run in background threads
    while (g_running) {
        std::this_thread::sleep_for(std::chrono::milliseconds(200));
    }
    
    // Wait for any ongoing SDK processing to complete
    if (g_sdk_processor && g_sdk_processor->isProcessing()) {
        LOG(INFO) << "Waiting for SDK processing to complete...";
        g_sdk_processor->waitForCompletion();
    }
    
    // Send shutdown notification
    metrics_server.broadcast(status_to_json("shutdown", "Presage daemon stopping"));
    
    // Cleanup global pointers
    g_metrics_server = nullptr;
    g_sdk_processor.reset();
    g_session_recorder.reset();
    
    LOG(INFO) << "Presage Daemon shutdown complete.";
    return 0;
}
