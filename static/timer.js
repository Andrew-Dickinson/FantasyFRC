
// variables for time units
var days, hours, minutes, seconds;

window.onload = function () {
	// get tag element
	var countdown = document.getElementById("countdown");

	// update the tag with id "countdown" every 1 second
	setInterval(function () {
		if (draft_active) {
			// find the amount of "seconds" between now and target
			var current_date = new Date().getTime();
			var seconds_left = target - Math.floor(current_date/1000);


			minutes = parseInt(seconds_left / 60);
			seconds = parseInt(seconds_left % 60);
			// format countdown string + set tag value

			if (Number(minutes)+Number(seconds) < 0) {
				countdown.innerHTML = ("0:00");
				location.replace("/draft/");
			} else {
				countdown.innerHTML = (minutes + ":" + ("0" + seconds).slice(-2));
			}
		}
	}, 1000);
};