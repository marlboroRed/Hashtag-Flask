// static/reward.js
document.addEventListener("DOMContentLoaded", () => {
    const rewardBtn = document.getElementById("reward-ad-button");
    if (rewardBtn) {
      rewardBtn.addEventListener("click", () => {
        fetch("/reward", { method: "POST" })
          .then(res => res.json())
          .then(data => alert(data.message))
          .catch(err => alert("오류 발생: " + err));
      });
    }
  });
  